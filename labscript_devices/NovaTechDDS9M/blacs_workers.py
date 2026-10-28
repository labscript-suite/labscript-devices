#####################################################################
#                                                                   #
# /labscript_devices/NovaTechDDS9M/blacs_workers.py                 #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################
import time
from blacs.tab_base_classes import Worker
from labscript_devices.NovaTechDDS9M.labscript_devices import bauds


class NovatechDDS9mWorker(Worker):
    def init(self):
        global serial; import serial
        global socket; import socket
        global h5py; import labscript_utils.h5_lock, h5py
        self.smart_cache = {'STATIC_DATA': None, 'TABLE_DATA': ''}
        
        if self.default_baud_rate is not None:
            initial_baud_rate = self.default_baud_rate
        else:
            initial_baud_rate = self.baud_rate

        self.connection = serial.Serial(
            self.com_port, baudrate=initial_baud_rate, timeout=0.1
        )
        
        # Check if the novatech will talk to us on this baud rate:
        if not self.check_connection():
            # Nope. Try all baud rates, from slowest to fastest:
            for rate in sorted(bauds):
                self.connection.baudrate = rate
                if self.check_connection():
                    # found it!
                    break
            else:
                # None of them worked.
                msg = "Error: tried all baud rates but got no response from NovaTech."
                raise RuntimeError(msg)

        # If the baud rate we are using to initially talk to the device is not the one
        # we want to use to program it, switch now to the desired baud rate:
        if self.connection.baudrate != self.baud_rate:
            self.connection.write(b'%s\r\n' % bauds[self.baud_rate])
            # ensure command finishes before switching rates in pyserial:
            time.sleep(0.1)
            self.connection.baudrate = self.baud_rate
            if not self.check_connection():
                msg = 'Error: Failed to execute command %s' % bauds[self.baud_rate]
                raise RuntimeError(msg)           
        
        # Set phase mode method
        phase_mode_commands = {
            'aligned': b'm a',
            'continuous': b'm n',
        }

        # Backward compat for shots compiled with phase_mode='default', which was based
        # on a misunderstanding of the working of the device and never did anything.
        phase_mode_commands['default'] = phase_mode_commands['continuous']

        self.phase_mode_command = phase_mode_commands[self.phase_mode]

        self.connection.write(b'e d\r\n')
        response = self.connection.readline()
        if response == b'e d\r\n':
            # if echo was enabled, then the command to disable it echos back at us!
            response = self.connection.readline()
        if response != b"OK\r\n":
            msg = 'Error: Failed to execute command: "e d", received "%s".' % response
            raise Exception(msg)

        self.connection.write(b'I a\r\n')
        if self.connection.readline() != b"OK\r\n":
            raise Exception('Error: Failed to execute command: "I a"')
        
        # Ensure we are in single-tone mode:
        self.connection.write(b'm 0\r\n')
        if self.connection.readline() != b"OK\r\n":
            raise Exception('Error: Failed to execute command: "m 0"')

        # Set the phase mode:
        self.connection.write(b'%s\r\n'%self.phase_mode_command)
        if self.connection.readline() != b"OK\r\n":
            raise Exception('Error: Failed to execute command: "%s"'%self.phase_mode.decode('utf8'))
        
        #return self.get_current_values()
        
    def check_connection(self):
        """Sends non-command and tests for correct response, returns True if connection
        appears to be working correctly, else returns False"""
        # check twice since false positive possible on first check. use readlines in
        # case echo is on
        self.connection.write(b'\r\n')
        self.connection.readlines()       
        self.connection.write(b'\r\n')
        try:
            return self.connection.readlines()[-1] == b'OK\r\n'
        except IndexError:
            # empty response, probably not connected
            return False

    def check_remote_values(self):
        # Get the currently output values:
        self.connection.write(b'QUE\r\n')
        try:
            response = [self.connection.readline() for i in range(5)]
        except socket.timeout:
            raise Exception('Failed to execute command "QUE". Cannot connect to device.')
        results = {}
        for i, line in enumerate(response[:4]):
            results['channel %d'%i] = {}
            freq, phase, amp, ignore, ignore, ignore, ignore = line.split()
            # Convert hex multiple of 0.1 Hz to MHz:
            results['channel %d'%i]['freq'] = float(int(freq,16))/10.0
            # Convert hex to int:
            results['channel %d'%i]['amp'] = int(amp,16)/1023.0
            # Convert hex fraction of 16384 to degrees:
            results['channel %d'%i]['phase'] = int(phase,16)*360/16384.0
        return results
        
    def program_manual(self,front_panel_values):
        # TODO: Optimise this so that only items that have changed are reprogrammed by storing the last programmed values
        # For each DDS channel,
        for i in range(4):    
            # and for each subchnl in the DDS,
            for subchnl in ['freq','amp','phase']:     
                # Program the sub channel
                self.program_static(i,subchnl,front_panel_values['channel %d'%i][subchnl])
        return self.check_remote_values()

    def program_static(self,channel,type,value):
        if type == 'freq':
            command = b'F%d %.7f\r\n'%(channel,value/10.0**6)
        elif type == 'amp':
            command = b'V%d %u\r\n'%(channel,int(value*1023+0.5))
        elif type == 'phase':
            command = b'P%d %u\r\n'%(channel,value*16384/360)
        else:
            raise TypeError(type)
        self.connection.write(command)
        if self.connection.readline() != b"OK\r\n":
            raise Exception('Error: Failed to execute command: %s' % command.decode('utf8'))
        # Now that a static update has been done, we'd better invalidate the saved STATIC_DATA:
        self.smart_cache['STATIC_DATA'] = None
     
    def transition_to_buffered(self,device_name,h5file,initial_values,fresh):

        # The "double clutch" trick: switching to table mode and back again, before
        # going into table mode for real, is observed empirically to resolve an
        # off-by-one error in table mode in some circumstances. Presumably it resets the
        # memory pointer of the device to zero (though it is a mystery why it would not
        # be zero already at this point)

        # Transition to table mode:
        self.connection.write(b'm t\r\n')
        self.connection.readline()
        # And back to manual mode
        self.connection.write(b'm 0\r\n')
        if self.connection.readline() != b"OK\r\n":
            raise Exception('Error: Failed to execute command: "m 0"')


        # Store the initial values in case we have to abort and restore them:
        self.initial_values = initial_values
        # Store the final values to for use during transition_to_static:
        self.final_values = {}
        static_data = None
        table_data = None
        with h5py.File(h5file, 'r') as hdf5_file:
            group = hdf5_file['/devices/'+device_name]
            # If there are values to set the unbuffered outputs to, set them now:
            if 'STATIC_DATA' in group:
                static_data = group['STATIC_DATA'][:][0]
            # Now program the buffered outputs:
            if 'TABLE_DATA' in group:
                table_data = group['TABLE_DATA'][:]
        
        if static_data is not None:
            data = static_data
            if fresh or data != self.smart_cache['STATIC_DATA']:
                self.logger.debug('Static data has changed, reprogramming.')
                self.smart_cache['STATIC_DATA'] = data
                self.connection.write(b'F2 %.7f\r\n'%(data['freq2']/10.0**7))
                self.connection.readline()
                self.connection.write(b'V2 %u\r\n'%(data['amp2']))
                self.connection.readline()
                self.connection.write(b'P2 %u\r\n'%(data['phase2']))
                self.connection.readline()
                self.connection.write(b'F3 %.7f\r\n'%(data['freq3']/10.0**7))
                self.connection.readline()
                self.connection.write(b'V3 %u\r\n'%data['amp3'])
                self.connection.readline()
                self.connection.write(b'P3 %u\r\n'%data['phase3'])
                self.connection.readline()
                
                # Save these values into final_values so the GUI can
                # be updated at the end of the run to reflect them:
                self.final_values['channel 2'] = {}
                self.final_values['channel 3'] = {}
                self.final_values['channel 2']['freq'] = data['freq2']/10.0
                self.final_values['channel 3']['freq'] = data['freq3']/10.0
                self.final_values['channel 2']['amp'] = data['amp2']/1023.0
                self.final_values['channel 3']['amp'] = data['amp3']/1023.0
                self.final_values['channel 2']['phase'] = data['phase2']*360/16384.0
                self.final_values['channel 3']['phase'] = data['phase3']*360/16384.0
                    
        # Now program the buffered outputs:
        if table_data is not None:
            data = table_data
            for i, line in enumerate(data):
                st = time.time()
                oldtable = self.smart_cache['TABLE_DATA']
                for ddsno in range(2):
                    if fresh or i >= len(oldtable) or (line['freq%d'%ddsno],line['phase%d'%ddsno],line['amp%d'%ddsno]) != (oldtable[i]['freq%d'%ddsno],oldtable[i]['phase%d'%ddsno],oldtable[i]['amp%d'%ddsno]):
                        self.connection.write(b't%d %04x %08x,%04x,%04x,ff\r\n'%(ddsno, i,line['freq%d'%ddsno],line['phase%d'%ddsno],line['amp%d'%ddsno]))
                        self.connection.readline()
                et = time.time()
                tt=et-st
                self.logger.debug('Time spent on line %s: %s', i, tt)
            # Store the table for future smart programming comparisons:
            try:
                self.smart_cache['TABLE_DATA'][:len(data)] = data
                self.logger.debug('Stored new table as subset of old table')
            except: # new table is longer than old table
                self.smart_cache['TABLE_DATA'] = data
                self.logger.debug('New table is longer than old table and has replaced it.')
                
            # Get the final values of table mode so that the GUI can
            # reflect them after the run:
            self.final_values['channel 0'] = {}
            self.final_values['channel 1'] = {}
            self.final_values['channel 0']['freq'] = data[-1]['freq0']/10.0
            self.final_values['channel 1']['freq'] = data[-1]['freq1']/10.0
            self.final_values['channel 0']['amp'] = data[-1]['amp0']/1023.0
            self.final_values['channel 1']['amp'] = data[-1]['amp1']/1023.0
            self.final_values['channel 0']['phase'] = data[-1]['phase0']*360/16384.0
            self.final_values['channel 1']['phase'] = data[-1]['phase1']*360/16384.0
            
            # Transition to table mode:
            self.connection.write(b'm t\r\n')
            self.connection.readline()
            if self.update_mode == 'synchronous':
                # Transition to hardware synchronous updates:
                self.connection.write(b'I e\r\n')
                self.connection.readline()
                # We are now waiting for a rising edge to trigger the output
                # of the second table pair (first of the experiment)
            elif self.update_mode == 'asynchronous':
                # Output will now be updated on falling edges.
                pass
            else:
                raise ValueError('invalid update mode %s'%str(self.update_mode))
                
            
        return self.final_values
    
    def abort_transition_to_buffered(self):
        return self.transition_to_manual(True)
        
    def abort_buffered(self):
        # TODO: untested
        return self.transition_to_manual(True)
    
    def transition_to_manual(self,abort = False):
        self.connection.write(b'm 0\r\n')
        if self.connection.readline() != b"OK\r\n":
            raise Exception('Error: Failed to execute command: "m 0"')
        self.connection.write(b'I a\r\n')
        if self.connection.readline() != b"OK\r\n":
            raise Exception('Error: Failed to execute command: "I a"')
        if abort:
            # If we're aborting the run, then we need to reset DDSs 2 and 3 to their initial values.
            # 0 and 1 will already be in their initial values. We also need to invalidate the smart
            # programming cache for them.
            values = self.initial_values
            DDSs = [2,3]
            self.smart_cache['STATIC_DATA'] = None
        else:
            # If we're not aborting the run, then we need to set DDSs 0 and 1 to their final values.
            # 2 and 3 will already be in their final values.
            values = self.final_values
            DDSs = [0,1]
            
        # only program the channels that we need to
        for ddsnumber in DDSs:
            channel_values = values['channel %d'%ddsnumber]
            for subchnl in ['freq','amp','phase']:            
                self.program_static(ddsnumber,subchnl,channel_values[subchnl])
            
        # return True to indicate we successfully transitioned back to manual mode
        return True
                     
    def shutdown(self):
        
        # return to the default baud rate
        if self.default_baud_rate is not None:
            self.connection.write(b'%s\r\n' % bauds[self.default_baud_rate])
            time.sleep(0.1)
            self.connection.readlines()        
        
        self.connection.close()
