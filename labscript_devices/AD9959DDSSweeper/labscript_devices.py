#####################################################################
#                                                                   #
# /labscript_devices/AD9959DDSSweeper/labscript_devices.py          #
#                                                                   #
# Copyright 2025, Carter Turnbaugh                                  #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################

from labscript import DDS, StaticDDS, IntermediateDevice, set_passed_properties, LabscriptError, config
from labscript_utils.unitconversions import NovaTechDDS9mFreqConversion, NovaTechDDS9mAmpConversion


import numpy as np
import sys

class AD9959DDSSweeper(IntermediateDevice):
    allowed_children = [DDS, StaticDDS]

    @set_passed_properties(
        property_names={
            'connection_table_properties': [
                'name',
                'com_port',
                'sweep_mode',
                'timing_mode',
                'ref_clock_external',
                'ref_clock_frequency',
                'pll_mult',
            ]
        }
    )

    def __init__(self, name, parent_device, com_port,
                 sweep_mode=0, timing_mode=0,
                 ref_clock_external=0, ref_clock_frequency=125e6, pll_mult=4, **kwargs):
        '''Labscript device class for AD9959 eval board controlled by a Raspberry Pi Pico running the DDS Sweeper firmware (https://github.com/QTC-UMD/dds-sweeper).

        '''
        IntermediateDevice.__init__(self, name, parent_device, **kwargs)
        self.BLACS_connection = '%s' % com_port
        
        # store mode data
        self.sweep_mode = sweep_mode
        self.timing_mode = timing_mode

        # Check clocking
        if ref_clock_frequency * pll_mult > 500e6:
            raise ValueError('DDS system clock frequency must be less than 500 MHz')
        elif pll_mult > 1 and ref_clock_frequency * pll_mult < 100e6:
            raise ValueError('DDS system clock frequency must be greater than 100 MHz when using PLL')
        elif not ref_clock_external and ref_clock_frequency > 133e6:
            raise ValueError('ref_clock_frequency must be less than 133 MHz when clock is provided by Pi Pico')

        self.dds_clock = ref_clock_frequency * pll_mult
        self.clk_scale = 2**32 / self.dds_clock
            
    def get_default_unit_conversion_classes(self, device):
        """Child devices call this during their __init__ (with themselves
        as the argument) to check if there are certain unit calibration
        classes that they should apply to their outputs, if the user has
        not otherwise specified a calibration class"""
        if device.connection in ['channel 0', 'channel 1', 'channel 2', 'channel 3']:
            # Default calibration classes for the non-static channels:
            return NovaTechDDS9mFreqConversion, NovaTechDDS9mAmpConversion, None
        else:
            return None, None, None

    def quantise_freq(self, data, device):
        """Provides bounds error checking and scales input values to instrument
        units (0.1 Hz) before ensuring uint32 integer type."""
        if not isinstance(data, np.ndarray):
            data = np.array(data)
        # Ensure that frequencies are within bounds:
        if np.any(data > self.dds_clock/2.) or np.any(data < 0.0):
            raise LabscriptError('%s %s ' % (device.description, device.name) +
                                 'can only have frequencies between 0.0Hz and %f MHz, ' + 
                                 'the limit imposed by %s.' % (self.name, self.dds_clock/2e6))
        scale_factor = self.clk_scale # Need to multiply by clk scale factor

        # It's faster to add 0.5 then typecast than to round to integers first:
        data = np.array((scale_factor*data)+0.5,dtype='<u4')
        return data, scale_factor
        
    def quantise_phase(self, data, device):
        """Ensures phase is wrapped about 360 degrees and scales to instrument
        units before type casting to uint16."""
        if not isinstance(data, np.ndarray):
            data = np.array(data)
        # ensure that phase wraps around:
        data %= 360
        # It's faster to add 0.5 then typecast than to round to integers first:
        scale_factor = 16384/360.0
        data = np.array((scale_factor*data)+0.5,dtype='<u2')
        return data, scale_factor
        
    def quantise_amp(self, data, device):
        """Ensures amplitude is within bounds and scales to instrument units
        (between 0 and 1023) before typecasting to uint16"""
        if not isinstance(data, np.ndarray):
            data = np.array(data)
        # ensure that amplitudes are within bounds:
        if np.any(data > 1 )  or np.any(data < 0):
            raise LabscriptError('%s %s ' % (device.description, device.name) +
                              'can only have amplitudes between 0 and 1 (Volts peak to peak approx), ' + 
                              'the limit imposed by %s.' % self.name)
        # It's faster to add 0.5 then typecast than to round to integers first:
        data = np.array((1023*data)+0.5,dtype='<u2')
        scale_factor = 1023
        return data, scale_factor

    def generate_code(self, hdf5_file):

        # external timing
        max_instructions_map = {
            'pico1' : 
                {
                'steps' : [16656, 8615, 5810, 4383],
                'sweeps' : [8614, 4382, 2938, 2210]
                },
            'pico2' : 
                {
                'steps' : [34132, 17654, 11905, 8981],
                'sweeps' : [17654, 8981, 6022, 4529]
                }
        }

        DDSs = {}
        stat_DDSs = {}
        num_channels = len(self.child_devices)

        # later we will need something better to support the other modes
        if self.sweep_mode > 0:
            mode = 'sweeps'
        else:
            mode = 'steps'

        for output in self.child_devices:
            # Check that the instructions will fit into RAM:
            max_instructions = max_instructions_map['pico1'][mode][num_channels-1]
            max_instructions -= 2 # -2 to include space for dummy instructions
            if isinstance(output, DDS) and len(output.frequency.raw_output) > max_instructions:
                raise LabscriptError(
                                    f'{self.name} can only support {max_instructions} instructions. \
                                    Please decrease the sample rates of devices on the same clock, \
                                    or connect {self.name} to a different pseudoclock.')
            try:
                prefix, channel = output.connection.split()
                channel = int(channel)
            except:
                raise LabscriptError('%s %s has invalid connection string: \'%s\'. ' % (output.description,output.name,str(output.connection)) + 
                                     'Format must be \'channel n\' with n from 0 to 4.')
            
            # separate dynamic from static
            if isinstance(output, DDS):
                DDSs[channel] = output
            elif isinstance(output, StaticDDS):
                stat_DDSs[channel] = output

        if not DDSs:
            # if no channels are being used, no need to continue
            return            

        for connection in DDSs:
            if connection in range(4):
                dds = DDSs[connection]   
                dds.frequency.raw_output, dds.frequency.scale_factor = self.quantise_freq(dds.frequency.raw_output, dds)
                dds.phase.raw_output, dds.phase.scale_factor = self.quantise_phase(dds.phase.raw_output, dds)
                dds.amplitude.raw_output, dds.amplitude.scale_factor = self.quantise_amp(dds.amplitude.raw_output, dds)
            else:
                raise LabscriptError('%s %s has invalid connection string: \'%s\'. ' % (dds.description,dds.name,str(dds.connection)) + 
                                     'Format must be \'channel n\' with n from 0 to 4.')

        dtypes = {'names':['%s%d' % (k, i) for i in DDSs for k in ['freq', 'amp', 'phase'] ],
                  'formats':[f for i in DDSs for f in ('<u4', '<u2', '<u2')]}

        clockline = self.parent_clock_line
        pseudoclock = clockline.parent_device
        times = pseudoclock.times[clockline]

        out_table = np.zeros(len(times), dtype=dtypes)

        for i, dds in DDSs.items():
            out_table['freq%d' % i][:] = dds.frequency.raw_output
            out_table['amp%d' % i][:] = dds.amplitude.raw_output
            out_table['phase%d' % i][:] = dds.phase.raw_output

        if stat_DDSs:
            # conversion to AD9959 units
            for connection in stat_DDSs:
                if connection in range(4):
                    dds = stat_DDSs[connection]   
                    dds.frequency.raw_output, dds.frequency.scale_factor = self.quantise_freq(dds.frequency.raw_output, dds)
                    dds.phase.raw_output, dds.phase.scale_factor = self.quantise_phase(dds.phase.raw_output, dds)
                    dds.amplitude.raw_output, dds.amplitude.scale_factor = self.quantise_amp(dds.amplitude.raw_output, dds)
                else:
                    raise LabscriptError('%s %s has invalid connection string: \'%s\'. ' % (dds.description,dds.name,str(dds.connection)) + 
                                        'Format must be \'channel n\' with n from 0 to 4.')
                
            static_dtypes = {
                'names':['%s%d' % (k, i) for i in stat_DDSs for k in ['freq', 'amp', 'phase'] ],
                'formats':[f for i in stat_DDSs for f in ('<u4', '<u2', '<u2')]
                }
            
            # print(f'Static dtypes: {static_dtypes}')
            static_table = np.zeros(1, dtype=static_dtypes)

            for connection in list(stat_DDSs.keys()):
                sdds = stat_DDSs[connection]
                static_table['freq%d' % connection] = sdds.frequency.raw_output[0]
                static_table['amp%d' % connection] = sdds.amplitude.raw_output[0]
                static_table['phase%d' % connection] = sdds.phase.raw_output[0]

        # write out data tables
        grp = self.init_device_group(hdf5_file)
        grp.create_dataset('dds_data', compression=config.compression, data=out_table)
        if stat_DDSs:
            grp.create_dataset('static_data', compression=config.compression, data=static_table)
        self.set_property('frequency_scale_factor', dds.frequency.scale_factor, location='device_properties')
        self.set_property('amplitude_scale_factor', dds.amplitude.scale_factor, location='device_properties')
        self.set_property('phase_scale_factor', dds.phase.scale_factor, location='device_properties')
