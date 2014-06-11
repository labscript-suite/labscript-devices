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
from labscript_devices import runviewer_parser, labscript_device, BLACS_tab, BLACS_worker

from labscript import IntermediateDevice, DDS, StaticDDS, Device, config, LabscriptError
from labscript_utils.unitconversions import NovaTechDDS9mFreqConversion, NovaTechDDS9mAmpConversion

import numpy as np
import labscript_utils.h5_lock, h5py
        
@labscript_device
class NovaTechDDS9M(IntermediateDevice):
    description = 'NT-DDS9M'
    allowed_children = [DDS, StaticDDS]
    clock_limit = 9990 # This is a realistic estimate of the max clock rate (100us for TS/pin10 processing to load next value into buffer and 100ns pipeline delay on pin 14 edge to update output values)

    
    def __init__(self, name, parent_device, com_port):
        IntermediateDevice.__init__(self, name, parent_device)
        self.BLACS_connection = com_port
    
    def add_device(self, device):
        Device.add_device(self, device)
        # The Novatech doesn't support 0Hz output; set the default frequency of the DDS to 0.1 Hz:
        device.frequency.default_value = 0.1
            
    def get_default_unit_conversion_classes(self, device):
        """Child devices call this during their __init__ (with themselves
        as the argument) to check if there are certain unit calibration
        classes that they should apply to their outputs, if the user has
        not otherwise specified a calibration class"""
        if device.connection in ['channel 0', 'channel 1']:
            # Default calibration classes for the non-static channels:
            return NovaTechDDS9mFreqConversion, NovaTechDDS9mAmpConversion, None
        else:
            return None, None, None
        
        
    def quantise_freq(self,data, device):
        # Ensure that frequencies are within bounds:
        if any(data > 171e6 )  or any(data < 0.1 ):
            raise LabscriptError('%s %s '%(device.description, device.name) +
                              'can only have frequencies between 0.1Hz and 171MHz, ' + 
                              'the limit imposed by %s.'%self.name)
        # It's faster to add 0.5 then typecast than to round to integers first:
        data = np.array((10*data)+0.5,dtype=np.uint32)
        scale_factor = 10
        return data, scale_factor
        
    def quantise_phase(self,data,device):
        # ensure that phase wraps around:
        data %= 360
        # It's faster to add 0.5 then typecast than to round to integers first:
        data = np.array((45.511111111111113*data)+0.5,dtype=np.uint16)
        scale_factor = 45.511111111111113
        return data, scale_factor
        
    def quantise_amp(self,data,device):
        # ensure that amplitudes are within bounds:
        if any(data > 1 )  or any(data < 0):
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
                dds = DDSs[connection]   
                dds.frequency.raw_output, dds.frequency.scale_factor = self.quantise_freq(dds.frequency.raw_output, dds)
                dds.phase.raw_output, dds.phase.scale_factor = self.quantise_phase(dds.phase.raw_output, dds)
                dds.amplitude.raw_output, dds.amplitude.scale_factor = self.quantise_amp(dds.amplitude.raw_output, dds)                   
            else:
                raise LabscriptError('%s %s has invalid connection string: \'%s\'. '%(dds.description,dds.name,str(dds.connection)) + 
                                     'Format must be \'channel n\' with n from 0 to 4.')
                                
        dtypes = [('freq%d'%i,np.uint32) for i in range(2)] + \
                 [('phase%d'%i,np.uint16) for i in range(2)] + \
                 [('amp%d'%i,np.uint16) for i in range(2)]
                 
        static_dtypes = [('freq%d'%i,np.uint32) for i in range(2,4)] + \
                        [('phase%d'%i,np.uint16) for i in range(2,4)] + \
                        [('amp%d'%i,np.uint16) for i in range(2,4)]
         
        clockline = self.parent_device
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
            
        grp = hdf5_file.create_group('/devices/'+self.name)
        grp.attrs['frequency_scale_factor'] = 10
        grp.attrs['amplitude_scale_factor'] = 1023
        grp.attrs['phase_scale_factor'] = 45.511111111111113
        grp.create_dataset('TABLE_DATA',compression=config.compression,data=out_table) 
        grp.create_dataset('STATIC_DATA',compression=config.compression,data=static_table) 



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
        
        # Store the COM port to be used
        self.com_port = str(self.settings['connection_table'].find_by_name(self.device_name).BLACS_connection)
        
        # Create and set the primary worker
        self.create_worker("main_worker",NovatechDDS9mWorker,{'com_port':self.com_port, 'baud_rate': 115200})
        self.primary_worker = "main_worker"

        # Set the capabilities of this device
        self.supports_remote_value_check(True)
        self.supports_smart_programming(True) 

@BLACS_worker        
class NovatechDDS9mWorker(Worker):
    def init(self):
        global serial; import serial
        global h5py; import labscript_utils.h5_lock, h5py
        self.smart_cache = {'STATIC_DATA': None, 'TABLE_DATA': ''}
        
        self.connection = serial.Serial(self.com_port, baudrate = self.baud_rate, timeout=0.1)
        self.connection.readlines()
        
        self.connection.write('e d\r\n')
        response = self.connection.readline()
        if response == 'e d\r\n':
            # if echo was enabled, then the command to disable it echos back at us!
            response = self.connection.readline()
        if response != "OK\r\n":
            raise Exception('Error: Failed to execute command: "e d". Cannot connect to the device.')
        
        self.connection.write('I a\r\n')
        if self.connection.readline() != "OK\r\n":
            raise Exception('Error: Failed to execute command: "I a"')
        
        self.connection.write('m 0\r\n')
        if self.connection.readline() != "OK\r\n":
            raise Exception('Error: Failed to execute command: "m 0"')
        
        #return self.get_current_values()
        
    def check_remote_values(self):
        # Get the currently output values:
        self.connection.write('QUE\r\n')
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
            command = 'F%d %.7f\r\n'%(channel,value/10.0**6)
            self.connection.write(command)
            if self.connection.readline() != "OK\r\n":
                raise Exception('Error: Failed to execute command: %s'%command)
        elif type == 'amp':
            command = 'V%d %u\r\n'%(channel,int(value*1023+0.5))
            self.connection.write(command)
            if self.connection.readline() != "OK\r\n":
                raise Exception('Error: Failed to execute command: %s'%command)
        elif type == 'phase':
            command = 'P%d %u\r\n'%(channel,value*16384/360)
            self.connection.write(command)
            if self.connection.readline() != "OK\r\n":
                raise Exception('Error: Failed to execute command: %s'%command)
        else:
            raise TypeError(type)
        # Now that a static update has been done, we'd better invalidate the saved STATIC_DATA:
        self.smart_cache['STATIC_DATA'] = None
     
    def transition_to_buffered(self,device_name,h5file,initial_values,fresh):
        # Store the initial values in case we have to abort and restore them:
        self.initial_values = initial_values
        # Store the final values to for use during transition_to_static:
        self.final_values = {}
        static_data = None
        table_data = None
        with h5py.File(h5file) as hdf5_file:
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
                self.connection.write('F2 %.7f\r\n'%(data['freq2']/10.0**7))
                self.connection.readline()
                self.connection.write('V2 %u\r\n'%(data['amp2']))
                self.connection.readline()
                self.connection.write('P2 %u\r\n'%(data['phase2']))
                self.connection.readline()
                self.connection.write('F3 %.7f\r\n'%(data['freq3']/10.0**7))
                self.connection.readline()
                self.connection.write('V3 %u\r\n'%data['amp3'])
                self.connection.readline()
                self.connection.write('P3 %u\r\n'%data['phase3'])
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
                        self.connection.write('t%d %04x %08x,%04x,%04x,ff\r\n '%(ddsno, i,line['freq%d'%ddsno],line['phase%d'%ddsno],line['amp%d'%ddsno]))
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
            self.connection.write('m t\r\n')
            self.connection.readline()
            # Transition to hardware updates:
            self.connection.write('I e\r\n')
            self.connection.readline()
            # We are now waiting for a rising edge to trigger the output
            # of the second table pair (first of the experiment)
        return self.final_values
    
    def abort_transition_to_buffered(self):
        return self.transition_to_manual(True)
        
    def abort_buffered(self):
        # TODO: untested
        return self.transition_to_manual(True)
    
    def transition_to_manual(self,abort = False):
        self.connection.write('m 0\r\n')
        if self.connection.readline() != "OK\r\n":
            raise Exception('Error: Failed to execute command: "m 0"')
        self.connection.write('I a\r\n')
        if self.connection.readline() != "OK\r\n":
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
        with h5py.File(self.path, 'r') as f:
            if 'TABLE_DATA' in f['devices/%s'%self.name]:
                table_data = f['devices/%s/TABLE_DATA'%self.name][:]
                for i in range(2):
                    for sub_chnl in ['freq', 'amp', 'phase']:                        
                        data['channel %d_%s'%(i,sub_chnl)] = table_data['%s%d'%(sub_chnl,i)][:]
                                
            if 'STATIC_DATA' in f['devices/%s'%self.name]:
                static_data = f['devices/%s/STATIC_DATA'%self.name][:]
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
    
