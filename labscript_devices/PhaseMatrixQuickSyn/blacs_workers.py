#####################################################################
#                                                                   #
# /labscript_devices/PhaseMatrixQuickSyn/blacs_workers.py           #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from blacs.tab_base_classes import Worker


class QuickSynWorker(Worker):
    def init(self):
        global serial; import serial
        global h5py; import labscript_utils.h5_lock, h5py
        global time; import time
    
        baud_rate=115200
        port = self.address
        self.connection = serial.Serial(port, baudrate = baud_rate, timeout=0.1)
        self.connection.readlines()
        
        #check to see if the reference is set to external. If not, make it so! (should we ask the user about this?)
        self.connection.write(b'ROSC:SOUR?\r')
        response = self.connection.readline().decode('utf8')
        if response == 'INT\n':
            #ref was set to internal, let's change it to ext
            self.connection.write(b'ROSC:SOUR EXT\r')
    
    def check_remote_values(self):
        # Get the currently output values:

        results = {'dds 0':{}}
        line = ''
        count = 0


        self.connection.write(b'FREQ?\r')
        line = self.connection.readline().decode('utf8')

        if line == '':
            #try again
            line = self.connection.readline().decode('utf8')
            if line == '':
                raise Exception("Device didn't say what its frequncy was :(")
            
        # Convert mHz to Hz:
        results['dds 0']['freq'] = float(line)/1000

        # wait a little while first, it doesn't like being asked things too quickly!
        time.sleep(0.05)
        self.connection.write(b'OUTP:STAT?\r')
        line = self.connection.readline().decode('utf8')
        if line == '':
            raise Exception("Device didn't say what its status was :(")
        time.sleep(0.05)    
            

        #get the gate status
        results['dds 0']['gate'] = 0 if line == 'OFF\n' else 1


        return results
    
    def check_status(self):
        results = {}
        line = ''
        self.connection.write(b'STAT?\r')
        line = self.connection.readline().decode('utf8')
        if line == '':
            raise Exception("Device didn't say what its status was :(")
        time.sleep(0.05)    
            
        
        #get the status and convert to binary, and take off the '0b' header:
        status = bin(int(line,16))[2:]
        # if the status is less than 8 bits long, pad the start with zeros!
        while len(status)<8:
            status = '0'+status
        # byte 0 is the 1 for an external ref, 0 for no external ref
        results['ref'] = int(status[-1])
        # byte 1 is high for rf unlocked, low for rf locked. This is silly, let's reverse it!
        results['freqlock'] = int(not int(status[-2]))
        # byte 2 is the high for ref unlocked, low for ref locked. Again, let's swap this!
        results['reflock'] = int(not int(status[-3]))
        # byte 3 tells us if the output is on or off,  we don't care since the check values function deals with this
        
        
        # byte 4 will go high if there is a voltage error.
        #In this case, we probably just want to raise an exception to get the user's attention
        if int(status[-5]):
            self.logger.critical('Device is reporting voltage error')
            raise Exception('Voltage error')
        # byte 5 tells us if the internal reference is being output
        results['ref_output'] = int(status[-6])
        # byte 6 tells us if blanking is on (i.e. turning off output while it changes frequency)
        results['blanking'] = int(status[-7])
        # byte 7 tells us if lock recovery is on,
        
        results['lock_recovery'] = int(status[-8])
        
        # now let's check it's temperature!
        self.connection.write(b'DIAG:MEAS? 21\r')
        results['temperature'] = float(self.connection.readline().decode('utf8'))
        
        # check if the temperature is bad, if it is, raise an exception. Hopefully one day this will be sent to syslog,
        #at which point we'll add some extra magic to segregate into warning and critical temperatures.
        
        if results['temperature'] > 50.0:
            raise Exception('WARNING: Temperature is too high! Temperature is %s'%results['temperature'])
            return results
        
        return results
    
    def program_manual(self,front_panel_values):
        freq = front_panel_values['dds 0']['freq']
        #program in millihertz:
        freq*=1e3
        command = 'FREQ %i\r'%freq
        self.connection.write(command.encode('utf8'))
        
        # add some sleep time here since the phasematrix gets grumpy
        time.sleep(0.05)
        
        
        gate = front_panel_values['dds 0']['gate']
        command = 'OUTP:STAT %i\r'%gate
        self.connection.write(command.encode('utf8'))
        
        return self.check_remote_values()
        
        
    def update_reference_out(self,value):
        pass
        
    def update_blanking(self,value):
        pass
        
    def update_lock_recovery(self,value):
        pass
    
    def transition_to_buffered(self,device_name,h5file,initial_values,fresh):
        # Store the initial values in case we have to abort and restore them:
        self.initial_values = initial_values
        # Store the final values to for use during transition_to_static:
        self.final_values = {}
        with h5py.File(h5file, 'r') as hdf5_file:
            group = hdf5_file['/devices/'+device_name]
            # If there are values to set the unbuffered outputs to, set them now:
            if 'STATIC_DATA' in group:
                data = group['STATIC_DATA'][:][0]
                
        self.connection.write(b'FREQ %i\r'%(data['freq0']))
        time.sleep(0.05)
        self.connection.write(b'OUTP:STAT 1\r')#%i'%(data['gate0']))
        
        
        # Save these values into final_values so the GUI can
        # be updated at the end of the run to reflect them:
        final_values = {'dds 0':{}}
        
        final_values['dds 0']['freq'] = data['freq0']/1e3
        final_values['dds 0']['gate'] = 1#data['gate0']
                
        return final_values
        
    def abort_transition_to_buffered(self):
        return self.transition_to_manual(True)
        
    def abort_buffered(self):
        return self.transition_to_manual(True)
    

    
    def transition_to_manual(self,abort = False):
        if abort:
            # If we're aborting the run, reset to original value
            self.program_manual(self.initial_values)
        # If we're not aborting the run, stick with buffered value. Nothing to do really!
        # return the current values in the device
        return True
        
    def shutdown(self):
        self.connection.close()
