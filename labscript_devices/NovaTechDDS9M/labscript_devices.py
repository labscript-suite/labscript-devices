#####################################################################
#                                                                   #
# /labscript_devices/NovaTechDDS9M/labscript_devices.py             #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################
from labscript import (
    IntermediateDevice,
    DDS,
    StaticDDS,
    Device,
    config,
    LabscriptError,
    set_passed_properties,
)
from labscript_utils.unitconversions import (
    NovaTechDDS9mFreqConversion,
    NovaTechDDS9mAmpConversion,
)
import numpy as np


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

    # This is longer than the technical requirement on the NovaTech. However, I
    # suspect the tri-state buffer or similar electronics that some groups have
    # in front of their NovaTech clock inputs might limit how fast this can be.
    # 1us should be a good compromise, but can always be overridden by a
    # subclass of monkey-patched if needed.
    minimum_clock_high_time = 1e-6

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
