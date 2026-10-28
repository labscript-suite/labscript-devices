#####################################################################
#                                                                   #
# /labscript_devices/PineBlaster/blacs_workers.py                   #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################
import labscript_utils.properties
from blacs.tab_base_classes import Worker


class PineblasterWorker(Worker):
    def init(self):
        global h5py; import labscript_utils.h5_lock, h5py
        global serial; import serial
        global time; import time
        self.smart_cache = []
    
        self.pineblaster = serial.Serial(self.usbport, 115200, timeout=1)
        # Device has a finite startup time:
        time.sleep(5)
        self.pineblaster.write(b'hello\r\n')
        response = self.pineblaster.readline().decode()
        
        if response == 'hello\r\n':
            return
        elif response:
            raise Exception('PineBlaster is confused: saying %s instead of hello'%(repr(response)))
        else:
            raise Exception('PineBlaster is not saying hello back when greeted politely. How rude. Maybe it needs a reboot.')
            
            
    def shutdown(self):
        self.pineblaster.close()
        
    def program_manual(self, values):    
        value = values['internal'] # there is only one value
        self.pineblaster.write(b'go high\r\n' if value else b'go low\r\n')
        response = self.pineblaster.readline().decode()
        assert response == 'ok\r\n', 'PineBlaster said \'%s\', expected \'ok\''%repr(response)
        return {}
        
    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):
        if fresh:
            self.smart_cache = []
        self.program_manual({'internal':0})
        
        with h5py.File(h5file,'r') as hdf5_file:
            group = hdf5_file['devices/%s'%device_name]
            pulse_program = group['PULSE_PROGRAM'][:]
            device_properties = labscript_utils.properties.get(hdf5_file, device_name, 'device_properties')
            self.is_master_pseudoclock = device_properties['is_master_pseudoclock']
            
        for i, instruction in enumerate(pulse_program):
            if i == len(self.smart_cache):
                # Pad the smart cache out to be as long as the program:
                self.smart_cache.append(None)
                
            # Only program instructions that differ from what's in the smart cache:
            if self.smart_cache[i] != instruction:
                self.pineblaster.write(b'set %d %d %d\r\n'%(i, instruction['period'], instruction['reps']))
                response = self.pineblaster.readline().decode()
                assert response == 'ok\r\n', 'PineBlaster said \'%s\', expected \'ok\''%repr(response)
                self.smart_cache[i] = instruction
                
        if not self.is_master_pseudoclock:
            # Get ready for a hardware trigger:
            self.pineblaster.write(b'hwstart\r\n')
            response = self.pineblaster.readline().decode()
            assert response == 'ok\r\n', 'PineBlaster said \'%s\', expected \'ok\''%repr(response)
            
        return {'internal':0} # always finish on 0
            
    def start_run(self):
        # Start in software:
        self.pineblaster.write(b'start\r\n')
        response = self.pineblaster.readline().decode()
        assert response == 'ok\r\n', 'PineBlaster said \'%s\', expected \'ok\''%repr(response)
    
    def status_monitor(self):
        # Wait to see if it's done within the timeout:
        response = self.pineblaster.readline().decode()
        if response:
            assert response == 'done\r\n'
            return True
        return False
        
    def transition_to_manual(self):
        # Wait until the pineblaster says it's done:
        if not self.is_master_pseudoclock:
            # If we're the master pseudoclock then this already happened
            # in status_monitor, so we don't need to do it again
            response = self.pineblaster.readline().decode()
            assert response == 'done\r\n', 'PineBlaster said \'%s\', expected \'ok\''%repr(response)
            # print 'done!'
        return True
    
    def abort_buffered(self):
        return self.abort()
    
    def abort_transition_to_buffered(self):
        return self.abort()
    
    def abort(self):
        self.pineblaster.write(b'restart\r\n')
        time.sleep(5)
        self.shutdown()
        self.init()
        return True
