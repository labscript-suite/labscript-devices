#####################################################################
#                                                                   #
# /NovaTechDDS9M.py                                                 #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################

from labscript_devices import runviewer_parser, BLACS_tab

from labscript import IntermediateDevice, DDS, StaticDDS, Device, config, LabscriptError, set_passed_properties
from labscript_utils.unitconversions import NovaTechDDS9mFreqConversion, NovaTechDDS9mAmpConversion

import numpy as np
import labscript_utils.h5_lock, h5py
import labscript_utils.properties

bauds = {9600: b'Kb 78', 
         19200: b'Kb 3c',
         38400: b'Kb 1e',
         57600: b'Kb 14',
         115200: b'Kb 0a'}

class NovaTechDDS9M(IntermediateDevice):
    """
    This class is initilzed with the key word argument  
    'update_mode' -- synchronous or asynchronous\
    'baud_rate',  -- operating baud rate
    'default_baud_rate' -- assumed baud rate at startup
    """
    description = 'NT-DDS9M'
    allowed_children = [DDS, StaticDDS]
    clock_limit = 9990 # This is a realistic estimate of the max clock rate (100us for TS/pin10 processing to load next value into buffer and 100ns pipeline delay on pin 14 edge to update output values)

    @set_passed_properties(
        property_names={
            'connection_table_properties': [
                'com_port',
                'baud_rate',
                'default_baud_rate',
                'update_mode',
                'synchronous_first_line_repeat',
                'phase_mode',
            ]
        }
    )
    def __init__(
        self,
        name,
        parent_device,
        com_port="",
        baud_rate=115200,
        default_baud_rate=None,
        update_mode='synchronous',
        synchronous_first_line_repeat=False,
        phase_mode='continuous',
        **kwargs
    ):
        IntermediateDevice.__init__(self, name, parent_device, **kwargs)
        self.BLACS_connection = '%s,%s'%(com_port, str(baud_rate))

        if not update_mode in ['synchronous', 'asynchronous']:
            raise LabscriptError('update_mode must be \'synchronous\' or \'asynchronous\'')            
        
        if not baud_rate in bauds:     
            raise LabscriptError('baud_rate must be one of {0}'.format(list(bauds)))            

        if not default_baud_rate in bauds and default_baud_rate is not None:     
            raise LabscriptError('default_baud_rate must be one of {0} or None (to indicate no default)'.format(list(bauds)))            

        if not phase_mode in ['aligned', 'continuous']:
            raise LabscriptError('phase_mode must be \'aligned\' or \'continuous\'')

        self.update_mode = update_mode
        self.phase_mode = phase_mode 
        self.synchronous_first_line_repeat = synchronous_first_line_repeat
        
    def add_device(self, device):
        Device.add_device(self, device)
        # The Novatech doesn't support 0Hz output; set the default frequency of the DDS to 0.1 Hz:
        device.frequency.default_value = 0.1
            
    def get_default_unit_conversion_classes(self, device):
        """Child devices call this during their __init__ (with themselves
        as the argument) to check if there are certain unit calibration
        classes that they should apply to their outputs, if the user has
        not otherwise specified a calibration class"""
        return NovaTechDDS9mFreqConversion, NovaTechDDS9mAmpConversion, None
        
    def quantise_freq(self, data, device):
        if not isinstance(data, np.ndarray):
            data = np.array(data)
        # Ensure that frequencies are within bounds:
        if np.any(data > 171e6 )  or np.any(data < 0.1 ):
            raise LabscriptError('%s %s '%(device.description, device.name) +
                              'can only have frequencies between 0.1Hz and 171MHz, ' + 
                              'the limit imposed by %s.'%self.name)
        # It's faster to add 0.5 then typecast than to round to integers first:
        data = np.array((10*data)+0.5,dtype=np.uint32)
        scale_factor = 10
        return data, scale_factor
        
    def quantise_phase(self, data, device):
        if not isinstance(data, np.ndarray):
            data = np.array(data)
        # ensure that phase wraps around:
        data %= 360
        # It's faster to add 0.5 then typecast than to round to integers first:
        data = np.array((45.511111111111113*data)+0.5,dtype=np.uint16)
        scale_factor = 45.511111111111113
        return data, scale_factor
        
    def quantise_amp(self,data,device):
        if not isinstance(data, np.ndarray):
            data = np.array(data)
        # ensure that amplitudes are within bounds:
        if np.any(data > 1 )  or np.any(data < 0):
            raise LabscriptError('%s %s '%(device.description, device.name) +
                              'can only have amplitudes between 0 and 1 (Volts peak to peak approx), ' + 
                              'the limit imposed by %s.'%self.name)
        # It's faster to add 0.5 then typecast than to round to integers first:
        data = np.array((1023*data)+0.5,dtype=np.uint16)
        scale_factor = 1023
        return data, scale_factor
        
    def generate_code(self, hdf5_file):
        DDSs = {}
        for output in self.child_devices:
            # Check that the instructions will fit into RAM:
            if isinstance(output, DDS) and len(output.frequency.raw_output) > 16384 - 2: # -2 to include space for dummy instructions
                raise LabscriptError('%s can only support 16383 instructions. '%self.name +
                                     'Please decrease the sample rates of devices on the same clock, ' + 
                                     'or connect %s to a different pseudoclock.'%self.name)
            try:
                prefix, channel = output.connection.split()
                channel = int(channel)
            except:
                raise LabscriptError('%s %s has invalid connection string: \'%s\'. '%(output.description,output.name,str(output.connection)) + 
                                     'Format must be \'channel n\' with n from 0 to 4.')
            DDSs[channel] = output
        for connection in DDSs:
            if connection in range(4):
                # Dynamic DDS
                dds = DDSs[connection]   
                dds.frequency.raw_output, dds.frequency.scale_factor = self.quantise_freq(dds.frequency.raw_output, dds)
                dds.phase.raw_output, dds.phase.scale_factor = self.quantise_phase(dds.phase.raw_output, dds)
                dds.amplitude.raw_output, dds.amplitude.scale_factor = self.quantise_amp(dds.amplitude.raw_output, dds)
            # elif connection in range(2,4):
                # # StaticDDS:
                # dds = DDSs[connection]   
                # dds.frequency.raw_output, dds.frequency.scale_factor = self.quantise_freq(dds.frequency.static_value, dds)
                # dds.phase.raw_output, dds.phase.scale_factor = self.quantise_phase(dds.phase.static_value, dds)
                # dds.amplitude.raw_output, dds.amplitude.scale_factor = self.quantise_amp(dds.amplitude.static_value, dds)
            else:
                raise LabscriptError('%s %s has invalid connection string: \'%s\'. '%(dds.description,dds.name,str(dds.connection)) + 
                                     'Format must be \'channel n\' with n from 0 to 4.')
                                
        dtypes = [('freq%d'%i,np.uint32) for i in range(2)] + \
                 [('phase%d'%i,np.uint16) for i in range(2)] + \
                 [('amp%d'%i,np.uint16) for i in range(2)]
                 
        static_dtypes = [('freq%d'%i,np.uint32) for i in range(2,4)] + \
                        [('phase%d'%i,np.uint16) for i in range(2,4)] + \
                        [('amp%d'%i,np.uint16) for i in range(2,4)]
         
        clockline = self.parent_clock_line
        pseudoclock = clockline.parent_device
        times = pseudoclock.times[clockline]
       
        out_table = np.zeros(len(times),dtype=dtypes)
        out_table['freq0'].fill(1)
        out_table['freq1'].fill(1)
        
        static_table = np.zeros(1, dtype=static_dtypes)
        static_table['freq2'].fill(1)
        static_table['freq3'].fill(1)
        
        for connection in range(2):
            if not connection in DDSs:
                continue
            dds = DDSs[connection]
            # The last two instructions are left blank, for BLACS
            # to fill in at program time.
            out_table['freq%d'%connection][:] = dds.frequency.raw_output
            out_table['amp%d'%connection][:] = dds.amplitude.raw_output
            out_table['phase%d'%connection][:] = dds.phase.raw_output
        for connection in range(2,4):
            if not connection in DDSs:
                continue
            dds = DDSs[connection]
            static_table['freq%d'%connection] = dds.frequency.raw_output[0]
            static_table['amp%d'%connection] = dds.amplitude.raw_output[0]
            static_table['phase%d'%connection] = dds.phase.raw_output[0]
            
        if self.update_mode == 'asynchronous' or self.synchronous_first_line_repeat:
            # Duplicate the first line of the table. Otherwise, we are one step
            # ahead in the table from the start of a run. In asynchronous
            # updating mode, this is necessary since the first line of the
            # table is already being output before the first trigger from
            # the master clock. When using a simple delay line for synchronous
            # output, this also seems to be required, in which case
            # synchronous_first_line_repeat should be set to True.
            # However, when a tristate driver is used as described at
            # http://labscriptsuite.org/blog/implementation-of-the-novatech-dds9m/
            # then is is not neccesary to duplicate the first line. Use of a
            # tristate driver in this way is the correct way to use
            # the novatech DDS, as per its instruction manual, and so is likely
            # to be the most reliable. However, through trial and error we've
            # determined that duplicating the first line like this gives correct
            # output in asynchronous mode and in synchronous mode when using a
            # simple delay line, at least for the specific device we tested.
            # Your milage may vary.
            out_table = np.concatenate([out_table[0:1], out_table])

        grp = self.init_device_group(hdf5_file)
        grp.create_dataset('TABLE_DATA',compression=config.compression,data=out_table) 
        grp.create_dataset('STATIC_DATA',compression=config.compression,data=static_table) 
        self.set_property('frequency_scale_factor', 10, location='device_properties')
        self.set_property('amplitude_scale_factor', 1023, location='device_properties')
        self.set_property('phase_scale_factor', 45.511111111111113, location='device_properties')



import time

from blacs.tab_base_classes import Worker, define_state
from blacs.tab_base_classes import MODE_MANUAL, MODE_TRANSITION_TO_BUFFERED, MODE_TRANSITION_TO_MANUAL, MODE_BUFFERED  

from blacs.device_base_class import DeviceTab

@BLACS_tab
class NovatechDDS9MTab(DeviceTab):
    def initialise_GUI(self):        
        # Capabilities
        self.base_units =    {'freq':'Hz',          'amp':'Arb',   'phase':'Degrees'}
        self.base_min =      {'freq':0.0,           'amp':0,       'phase':0}
        self.base_max =      {'freq':170.0*10.0**6, 'amp':1,       'phase':360}
        self.base_step =     {'freq':10**6,         'amp':1/1023., 'phase':1}
        self.base_decimals = {'freq':1,             'amp':4,       'phase':3} # TODO: find out what the phase precision is!
        self.num_DDS = 4
        
        # Create DDS Output objects
        dds_prop = {}
        for i in range(self.num_DDS): # 4 is the number of DDS outputs on this device
            dds_prop['channel %d'%i] = {}
            for subchnl in ['freq', 'amp', 'phase']:
                dds_prop['channel %d'%i][subchnl] = {'base_unit':self.base_units[subchnl],
                                                     'min':self.base_min[subchnl],
                                                     'max':self.base_max[subchnl],
                                                     'step':self.base_step[subchnl],
                                                     'decimals':self.base_decimals[subchnl]
                                                    }
        # Create the output objects    
        self.create_dds_outputs(dds_prop)        
        # Create widgets for output objects
        dds_widgets,ao_widgets,do_widgets = self.auto_create_widgets()
        # and auto place the widgets in the UI
        self.auto_place_widgets(("DDS Outputs",dds_widgets))
        
        connection_object = self.settings['connection_table'].find_by_name(self.device_name)
        connection_table_properties = connection_object.properties
        
        self.phase_mode = connection_table_properties.get('phase_mode', 'continuous')

        self.com_port = connection_table_properties.get('com_port', None)
        self.baud_rate = connection_table_properties.get('baud_rate', None)
        self.default_baud_rate = connection_table_properties.get('default_baud_rate', None)
        self.update_mode = connection_table_properties.get('update_mode', 'synchronous')
        
        # Backward compat:
        blacs_connection =  str(connection_object.BLACS_connection)
        if ',' in blacs_connection:
            com_port, baud_rate = blacs_connection.split(',')
            if self.com_port is None:
                self.com_port = com_port
            if self.baud_rate is None:
                self.baud_rate = int(baud_rate)
        else:
            self.com_port = blacs_connection
            self.baud_rate = 115200
        


        # Create and set the primary worker
        self.create_worker("main_worker",NovatechDDS9mWorker,{'com_port':self.com_port,
                                                              'baud_rate': self.baud_rate,
                                                              'default_baud_rate': self.default_baud_rate,
                                                              'update_mode': self.update_mode,
                                                              'phase_mode': self.phase_mode})
        self.primary_worker = "main_worker"

        # Set the capabilities of this device
        self.supports_remote_value_check(True)
        self.supports_smart_programming(True) 


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
                self.logger.debug('Time spent on line %s: %s'%(i,tt))
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
        
        
        
@runviewer_parser
class RunviewerClass(object):    
    def __init__(self, path, device):
        self.path = path
        self.name = device.name
        self.device = device
            
    def get_traces(self, add_trace, clock=None):
        if clock is None:
            # we're the master pseudoclock, software triggered. So we don't have to worry about trigger delays, etc
            raise Exception('No clock passed to %s. The NovaTechDDS9M must be clocked by another device.'%self.name)
        
        times, clock_value = clock[0], clock[1]
        
        clock_indices = np.where((clock_value[1:]-clock_value[:-1])==1)[0]+1
        # If initial clock value is 1, then this counts as a rising edge (clock should be 0 before experiment)
        # but this is not picked up by the above code. So we insert it!
        if clock_value[0] == 1:
            clock_indices = np.insert(clock_indices, 0, 0)
        clock_ticks = times[clock_indices]
        
        # get the data out of the H5 file
        data = {}
        with h5py.File(self.path, 'r') as hdf5_file:
            if 'TABLE_DATA' in hdf5_file['devices/%s' % self.name]:
                table_data = hdf5_file['devices/%s/TABLE_DATA' % self.name][:]
                connection_table_properties = labscript_utils.properties.get(hdf5_file, self.name, 'connection_table_properties')
                update_mode = getattr(connection_table_properties, 'update_mode', 'synchronous')
                synchronous_first_line_repeat = getattr(connection_table_properties, 'synchronous_first_line_repeat', False)
                if update_mode == 'asynchronous' or synchronous_first_line_repeat:
                    table_data = table_data[1:]
                for i in range(2):
                    for sub_chnl in ['freq', 'amp', 'phase']:
                        data['channel %d_%s'%(i,sub_chnl)] = table_data['%s%d'%(sub_chnl,i)][:]
                                
            if 'STATIC_DATA' in hdf5_file['devices/%s'%self.name]:
                static_data = hdf5_file['devices/%s/STATIC_DATA'%self.name][:]
                for i in range(2,4):
                    for sub_chnl in ['freq', 'amp', 'phase']:
                        data['channel %d_%s'%(i,sub_chnl)] = np.empty((len(clock_ticks),))
                        data['channel %d_%s'%(i,sub_chnl)].fill(static_data['%s%d'%(sub_chnl,i)][0])
            
        
        for channel, channel_data in data.items():
            data[channel] = (clock_ticks, channel_data)
        
        for channel_name, channel in self.device.child_list.items():
            for subchnl_name, subchnl in channel.child_list.items():
                connection = '%s_%s'%(channel.parent_port, subchnl.parent_port)
                if connection in data:
                    add_trace(subchnl.name, data[connection], self.name, connection)
        
        return {}

