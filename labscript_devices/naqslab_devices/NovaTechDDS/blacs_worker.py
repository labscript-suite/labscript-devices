#####################################################################
#                                                                   #
# /naqslab_devices/NovaTechDDS/blacs_worker.py                      #
#                                                                   #
# Copyright 2018, David Meyer                                       #
#                                                                   #
# This file is part of naqslab_devices,                             #
# and is licensed under the                                         #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
# Source borrows heavily from labscript_devices/NovaTechDDS9m       #
#                                                                   #
#####################################################################
from labscript import LabscriptError
from blacs.tab_base_classes import Worker

import time
import numpy as np
import serial
import socket
import labscript_utils.h5_lock, h5py

       
class NovaTech409B_ACWorker(Worker):
    def init(self):
        """Initialization command run automatically by the BLACS tab on 
        startup. It establishes communication and sends initial default 
        configuration commands"""
        self.smart_cache = {'STATIC_DATA': None, 'TABLE_DATA': '',
                                'CURRENT_DATA':None}
        self.baud_dict = {9600:b'78', 19200:b'3c', 38400:b'1e',57600:b'14',115200:b'0a'}
        
        self.err_codes = {b'?0':'Unrecognized Command',
                          b'?1':'Bad Frequency',
                          b'?2':'Bad AM Command',
                          b'?3':'Input Line Too Long',
                          b'?4':'Bad Phase',
                          b'?5':'Bad Time',
                          b'?6':'Bad Mode',
                          b'?7':'Bad Amp',
                          b'?8':'Bad Constant',
                          b'?f':'Bad Byte'}
        
        # total number of DDS channels on device & channel properties
        self.N_chan = 4
        self.subchnls = ['freq','amp','phase']
        
        # conversion dictionaries for program_static from 
        # program_manual                      
        self.conv = {'freq':self.clk_scale*10**(-6),'amp':1023.0,'phase':16384.0/360.0}## check if things break 2019-02-22
        # and from transition_to_buffered
        self.conv_buffered = {'freq':10**(-7),'amp':1,'phase':1}
        # read from device conversion, basically conv_buffered/conv
        self.read_conv = {'freq':1/(self.clk_scale*10.0),'amp':1/1023.0,'phase':360.0/16384.0} ## check if things break 2019-02-22
        
        # set phase mode method
        phase_mode_commands = {
            'aligned': b'm a',
            'continuous': b'm n'}
        self.phase_mode_command = phase_mode_commands[self.phase_mode]
        
        self.connection = serial.Serial(self.com_port, baudrate = self.baud_rate, timeout=0.1)
        self.connection.readlines()
        
        # to configure baud rate, must determine current device baud rate
        # first check desired, since it's most likely
        connected, response = self.check_connection()
        if not connected:
            # not already set
            bauds = list(self.baud_dict)
            if self.baud_rate in bauds:
                bauds.remove(self.baud_rate)
            else:
                raise LabscriptError('%d baud rate not supported by Novatech 409B' % self.baud_rate)
                
            # iterate through other baud-rates to find current
            for rate in bauds:
                self.connection.baudrate = rate
                connected, response = self.check_connection()
                if connected:
                    # found it!
                    break
            else:
                raise LabscriptError('Error: Baud rate not found! Is Novatech DDS connected?')
            
            # now we can set the desired baud rate
            baud_string = b'Kb %s\r\n' % (self.baud_dict[self.baud_rate])
            self.connection.write(baud_string)
            # ensure command finishes before switching rates in pyserial
            time.sleep(0.1)
            self.connection.baudrate = self.baud_rate
            connected, response = self.check_connection()
            if not connected:
                raise LabscriptError('Error: Failed to execute command "%s"' % baud_string.decode('utf8'))           
        
        self.connection.write(b'e d\r\n')
        response = self.connection.readline()
        if response == b'e d\r\n':
            # if echo was enabled, then the command to disable it echos back at us!
            response = self.connection.readline()
        if response != b'OK\r\n':
            raise Exception('Error: Failed to execute command: "e d". Cannot connect to the device.')
        
        # set automatic updates and phase mode
        self.write_check(b'M 0\r\n')
        self.write_check(b'I a\r\n')
        self.write_check(b'%s\r\n'%self.phase_mode_command)
        
        # Set clock parameters
        if self.R_option:
            # Using R option. Do not send C or Kp serial commands
            pass
        else:
            # Pass kp value
            self.write_check(b'Kp %02x\r\n'%self.kp)
            # Pass clock setting            
            if self.ext_clk:
                # Enable external clock
                clk_command = b'C E\r\n'              
            else:
                # Or enable internal clock
                clk_command = b'C I\r\n'
            self.write_check(clk_command)   
        
        # populate the 'CURRENT_DATA' dictionary    
        self.check_remote_values()
     
    def check_connection(self):
        '''Sends non-command and tests for correct response
        returns tuple of connection state and reponse string'''
        # check twice since false positive possible on first check
        # use readlines in case echo is on
        self.connection.write(b'\r\n')
        self.connection.readlines()       
        self.connection.write(b'\r\n')
        try:
            response = self.connection.readlines()[-1]
            connected = response == b'OK\r\n'
        except IndexError:
            # empty response, probably not connected
            connected = False
            response = b''
        
        return connected, response
        
    def write_check(self,command):
        '''Sends command and checks and confirms proper execution
        by reading 'OK' from device.'''
        self.connection.write(command)
        response = self.check_error(self.connection.readline())
        if response != b'OK\r\n':
            msg = '''Command "%s" did not execute properly.'''%command.decode('utf8')
            raise Exception(dedent(msg))
        
    def check_error(self,response):
        '''Parse response for errors and raise appropriate error.
        If no error, returns response unaltered.'''
        if b'?' in response:
            # there is an error in the response, 
            # get code number after ?
            code = response.split(b'?',1)[-1][0]
            try:
                msg = 'NovaTech DDS at %s has error %s\n'%(
                        self.com_port,self.err_codes[b'?'+code])
            except KeyError:
                msg = 'NovaTech DDS at %s has unrecognized error %s\n'%(
                        self.com_port,response.decode('utf8'))
            # clear the read buffer before breaking
            self.connection.readlines()
            raise Exception(dedent(msg))
        
        # if we didn't break, no error so return response
        return response
        
    def check_remote_values(self):
        """Queries device for current output settings. Return results as a 
        dictionary to update the BLACS tab."""
        self.connection.write(b'QUE\r\n')
        try:
            response = [self.connection.readline() for i in range(self.N_chan+1)]
        except socket.timeout:
            raise Exception('Failed to execute command "QUE". Cannot connect to device.')
        results = {}
        for i, line in enumerate(response[:self.N_chan]):
            results['channel %d' % i] = {}
            freq, phase, amp, ignore, ignore, ignore, ignore = line.split()
            # Convert hex multiple of 0.1 Hz to Hz:
            # Limit precision after converstion to 0.1 Hz
            results['channel %d' % i]['freq'] = round(float(int(freq,16))*self.read_conv['freq'],1)
            # Convert hex to int:
            results['channel %d' % i]['amp'] = int(amp,16)*self.read_conv['amp']
            # Convert hex fraction of 16384 to degrees:
            results['channel %d' % i]['phase'] = int(phase,16)*self.read_conv['phase']
            
            self.smart_cache['CURRENT_DATA'] = results
        return results
        
    def program_manual(self,front_panel_values):
        """Called within the BLACS worker during transitions. This calls
        program_static for each setting if it isn't already set."""
        for i in range(self.N_chan):
            # and for each subchnl in the DDS,
            for subchnl in self.subchnls:
                # don't program if setting is the same
                if self.smart_cache['CURRENT_DATA']['channel %d' % i][subchnl] == front_panel_values['channel %d' % i][subchnl]:
                    continue       
                # Program the sub channel
                self.program_static(i,subchnl,
                    front_panel_values['channel %d' % i][subchnl]*self.conv[subchnl])
                # Now that a static update has been done, 
                # we'd better invalidate the saved STATIC_DATA for the channel:
                self.smart_cache['STATIC_DATA'] = None
        return self.check_remote_values()

    def program_static(self,channel,type,value):
        """General output parameter programming function. 
        Only sends one command per use."""            
        if type == 'freq':
            command = b'F%d %.7f\r\n' % (channel,value)
        elif type == 'amp':
            command = b'V%d %d\r\n' % (channel,int(value))
        elif type == 'phase':
            command = b'P%d %d\r\n' % (channel,int(value))
        else:
            raise TypeError(type)
        
        self.write_check(command)
     
    def transition_to_buffered(self,device_name,h5file,initial_values,fresh):
                
        # Store the initial values in case we have to abort and restore them:
        self.initial_values = initial_values
        # Store the final values for use during transition_to_static:
        self.final_values = initial_values
        static_data = None
        table_data = None
        with h5py.File(h5file,'r') as hdf5_file:
            group = hdf5_file['/devices/'+device_name]
            # If there are values to set the unbuffered outputs to, set them now:
            if 'STATIC_DATA' in group:
                static_data = group['STATIC_DATA'][:][0]
            # Now program the buffered outputs:
            if 'TABLE_DATA' in group:
                table_data = group['TABLE_DATA'][:]
                # using table mode, need to reset memory pointer to zero
                # Transition to table mode:
                self.connection.write(b'M t\r\n')
                self.connection.readline()
                # And back to manual mode
                self.connection.write(b'M 0\r\n')
                if self.connection.readline() != b"OK\r\n":
                    raise Exception('Error: Failed to execute command: "%s"' % self.phase_mode_command.decode('utf8'))
                
        if static_data is not None:
            data = static_data
            if fresh or data != self.smart_cache['STATIC_DATA']:
                self.smart_cache['STATIC_DATA'] = data
                                
                # need to infer which channels to program
                num_chan = len(data)//len(self.subchnls)
                channels = [int(name[-1]) for name in data.dtype.names[0:num_chan]]
                
                for i in channels:
                    for subchnl in self.subchnls:
                        curr_value = self.smart_cache['CURRENT_DATA']['channel %d' % i][subchnl]*self.conv[subchnl]
                        value = data[subchnl+str(i)]*self.conv_buffered[subchnl]
                        if value == curr_value:
                            continue
                        else:
                            self.program_static(i,subchnl,value)
                            if subchnl == 'freq':
                                self.final_values['channel %d'%i][subchnl] = round(value/self.conv[subchnl],1)
                                self.smart_cache['CURRENT_DATA']['channel %d'%i][subchnl] = round(value*self.read_conv[subchnl],1)
                            else:
                                self.final_values['channel %d'%i][subchnl] = value/self.conv[subchnl]
                                self.smart_cache['CURRENT_DATA']['channel %d'%i][subchnl] = value*self.read_conv[subchnl]
                    
        # Now program the buffered outputs:
        if table_data is not None:
            data = table_data
            for i, line in enumerate(data):
                st = time.time()
                oldtable = self.smart_cache['TABLE_DATA']
                for ddsno in range(2):
                    if fresh or i >= len(oldtable) or (line['freq%d'%ddsno],line['phase%d'%ddsno],line['amp%d'%ddsno]) != (oldtable[i]['freq%d'%ddsno],oldtable[i]['phase%d'%ddsno],oldtable[i]['amp%d'%ddsno]):
                        self.connection.write(b't%d %04x %08x,%04x,%04x,ff\r\n'%(ddsno, i,line['freq%d'%ddsno],line['phase%d'%ddsno],line['amp%d'%ddsno]))
                        self.check_error(self.connection.readline()) # speed this up by block writing and reading and don't check errors
                et = time.time()
                tt=et-st
                self.logger.debug('Time spent on line %s: %s' % (i,tt))
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
            self.final_values['channel 0']['freq'] = round(data[-1]['freq0']*self.read_conv['freq'],1)
            self.final_values['channel 1']['freq'] = round(data[-1]['freq1']*self.read_conv['freq'],1)
            self.final_values['channel 0']['amp'] = data[-1]['amp0']*self.read_conv['amp']
            self.final_values['channel 1']['amp'] = data[-1]['amp1']*self.read_conv['amp']
            self.final_values['channel 0']['phase'] = data[-1]['phase0']*self.read_conv['phase']
            self.final_values['channel 1']['phase'] = data[-1]['phase1']*self.read_conv['phase']
            
            # Transition to table mode:
            self.write_check(b'm t\r\n')
            if self.update_mode == 'synchronous':
                # Transition to hardware synchronous updates:
                self.write_check(b'I e\r\n')
                # We are now waiting for a rising edge to trigger the output
                # of the second table pair (first of the experiment)
            elif self.update_mode == 'asynchronous':
                # Output will now be updated on falling edges.
                pass
            else:
                raise ValueError('invalid update mode %s'%self.update_mode.decode('utf8'))
                
            
        return self.final_values
    
    def abort_transition_to_buffered(self):
        return self.transition_to_manual(True)
        
    def abort_buffered(self):
        # TODO: untested
        return self.transition_to_manual(True)
    
    def transition_to_manual(self,abort = False):
        self.write_check(b'M 0\r\n')
        self.write_check(b'I a\r\n')

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
        for channel in values:
            ddsnum = int(channel.split(' ')[-1])
            if ddsnum not in DDSs:
                continue
            for subchnl in self.subchnls:            
                self.program_static(ddsnum,subchnl,values[channel][subchnl]*self.conv[subchnl])
            
        # return True to indicate we successfully transitioned back to manual mode
        return True
                     
    def shutdown(self):
        self.connection.close()        
    
class NovaTech409BWorker(NovaTech409B_ACWorker):
    
    def transition_to_manual(self,abort = False):
        if abort:
            # If we're aborting the run, then we need to reset DDSs to their initial values.
            # We also need to invalidate the smart programming cache for them.
            self.smart_cache['STATIC_DATA'] = None
            for channel in self.initial_values:
                ddsnum = int(channel.split(' ')[-1])
                for subchnl in self.subchnls:
                    self.program_static(ddsnum,subchnl,self.initial_values[channel][subchnl]*self.conv[subchnl])
        else:
            # if not aborting, final values already set so do nothing
            pass
        # return True to indicate we successfully transitioned back to manual mode
        return True

class NovaTech440AWorker(NovaTech409BWorker):
    
    def init(self):
        """Modified init from 409B-AC. The 440A only supports one baud rate
        and does not support output mode commands."""
        self.smart_cache = {'STATIC_DATA': None,'CURRENT_DATA':None}
        
        self.N_chan = 1
        self.subchnls = ['freq','phase']
        
        # conversion dictionaries for program_static from 
        # program_manual                      
        self.conv = {'freq':10**(-6),'phase':16384.0/360.0}
        # and from transition_to_buffered
        self.conv_buffered = {'freq':10**(-6),'phase':1}
        # read from device conversion, nominally conv_buffered/conv
        self.read_conv = {'freq':1/4.0,'phase':360.0/16384.0}
        
        self.connection = serial.Serial(self.com_port, baudrate = self.baud_rate, timeout=0.1)
        self.connection.readlines()
        
        self.connection.write(b'e d\r\n')
        response = self.connection.readline()
        
        if response == b'e d\r\n':
            # if echo was enabled, then the command to disable it echos back at us!
            response = self.connection.readline()
        if response != b'OK\r\n':
            raise Exception('Error: Failed to execute command: "e d". Cannot connect to the device.')
            
        # configure external clocking
        if self.ext_clk:
            self.write_check(b'Fr %.3f\r\n' % self.clk_freq)
            self.write_check(b'C E\r\n')
        else:
            self.write_check(b'C D\r\n')
            
        # populate the 'CURRENT_DATA' dictionary    
        self.check_remote_values()
        
    def program_static(self,channel,type,value):
        """General output parameter programming function. Only sends one command
        per use."""            
        if type == 'freq':
            command = b'F%d %.6f\r\n' % (channel,value) #only 6 decimal places for 440A
        elif type == 'phase':
            command = b'P%d %d\r\n' % (channel,int(value))
        else:
            raise TypeError(type)
        self.write_check(command)

    def check_remote_values(self):
        """The 440A Query command returns values in a different order and does
        not tell the amplitude."""
        # Get the currently output values:
        self.connection.write(b'QUE\r\n')
        try:
            response = self.check_error(self.connection.readline())
        except socket.timeout:
            raise Exception('Failed to execute command "QUE". Cannot connect to device.')
        
        results = {}
        results['channel 0'] = {}
        phase, freq, ignore, ignore, ignore, ignore = response.split()
        # Convert hex multiple in 0.25 Hz units to Hz:
        results['channel 0']['freq'] = float(int(freq,16))*self.read_conv['freq']

        # Convert hex fraction of 16384 to degrees:
        results['channel 0']['phase'] = int(phase,16)*self.read_conv['phase']
            
        self.smart_cache['CURRENT_DATA'] = results
        
        return results
