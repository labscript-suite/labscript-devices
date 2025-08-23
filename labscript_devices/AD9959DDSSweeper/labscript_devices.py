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

class AD9959DDSSweeper(IntermediateDevice):
    allowed_children = [DDS, StaticDDS]
    allowed_boards = ['pico1', 'pico2']
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
    
    cycles_per_instruction_map = {
        'steps' : [500, 750, 1000, 1250],
        'sweeps' : [1000, 1500, 2000, 2500]
    }

    @set_passed_properties(
        property_names={
            'connection_table_properties': [
                'name',
                'com_port',
                'pico_board',
                'sweep_mode',
                'ref_clock_external',
                'ref_clock_frequency',
                'pll_mult',
            ]
        }
    )

    def __init__(self, name, parent_device, com_port, dynamic_channels,
                 pico_board='pico1', sweep_mode=0,
                 ref_clock_external=0, ref_clock_frequency=125e6, pll_mult=4, **kwargs):
        '''Labscript device class for AD9959 eval board controlled by a Raspberry Pi Pico running the DDS Sweeper firmware (https://github.com/QTC-UMD/dds-sweeper).

        This labscript device provides up to four channels of DDS outputs. It is designed to be connected to a pseudoclock clockline.

        Args:
            name (str): python variable name to assign to the AD9959DDSSweeper
            parent_device (:class:`~.ClockLine`):
                Pseudoclock clockline used to clock DDS parameter changes.
            com_port (str): COM port assigned to the AD9959DDSSweeper by the OS.
                On Windows, takes the form of `COMd` where `d` is an integer.
            dynamic_channels (int): number of dynamic DDS channels that will be added.
                This must be specified in the constructor so that update rates can be calculated correctly.
            pico_board (str): The version of pico board used, pico1 or pico2.
            sweep_mode (int):
                The DDS Sweeper firmware can set the DDS outputs in either fixed steps or sweeps of the amplitude, frequency, or phase.
                At this time, only steps are supported, so sweep_mode must be 0.
            ref_clock_external (int): Set to 0 to have Pi Pico provide the reference clock to the AD9959 eval board. Set to 1 for another source of reference clock for the AD9959 eval board.
            ref_clock_frequency (float): Frequency of the reference clock. If ref_clock_external is 0, the Pi Pico system clock will be set to this frequency. If the PLL is used, ref_clock_frequency * pll_mult must be between 100 MHz and 500 MHz. If the PLL is not used, ref_clock_frequency must be less than 500 MHz.
            pll_mult: the AD9959 has a PLL to multiply the reference clock frequency. Allowed values are 1 or 4-20.
        '''
        self.BLACS_connection = '%s' % com_port
        
        if pico_board in self.allowed_boards:
            self.pico_board = pico_board
        else:
            raise LabscriptError(f'Pico board specified not in {self.allowed_boards}')
        
        # store mode data
        self.sweep_mode = sweep_mode
        self.ref_clock_frequency = ref_clock_frequency
        # Check clocking
        if ref_clock_frequency * pll_mult > 500e6:
            raise ValueError('DDS system clock frequency must be less than 500 MHz')
        elif pll_mult > 1 and ref_clock_frequency * pll_mult < 100e6:
            raise ValueError('DDS system clock frequency must be greater than 100 MHz when using PLL')
        elif not ref_clock_external and ref_clock_frequency > 133e6:
            raise ValueError('ref_clock_frequency must be less than 133 MHz when clock is provided by Pi Pico')

        self.dds_clock = ref_clock_frequency * pll_mult
        # define output scale factors for dynamic channels
        # static channel scaling handled by firmware
        self.freq_scale = 2**32 / self.dds_clock
        self.amp_scale = 1023
        self.phase_scale = 16384/360.0

        # Store number of dynamic channels
        if dynamic_channels > 4:
            raise ValueError('AD9959DDSSweeper only supports up to 4 total channels, dynamic channels must be 4 or less.')
        self.dynamic_channels = dynamic_channels

        IntermediateDevice.__init__(self, name, parent_device, **kwargs)

    @property
    def clock_limit(self):
        '''Dynamically computs clock limit based off of number of dynamic 
        channels and reference clock frequency.'''
        if self.dynamic_channels == 0:
            # No clock limit
            return None
        
        if self.sweep_mode > 0:
            mode = 'sweeps'
        else:
            mode = 'steps'
        try:
            cycles_per_instruction = self.cycles_per_instruction_map[mode][self.dynamic_channels - 1]
        except (KeyError, IndexError):
            raise LabscriptError(f'Unsupported mode or number of channels: {mode}, {self.dynamic_channels}')

        return self.ref_clock_frequency / cycles_per_instruction

    def add_device(self, device):
        """Confirms channel specified is valid before adding

        Validity checks include channel name and static/dynamic status.
        Dynamic channels must be specified before static channels.
        Args:
            device(): Device to attach. Must be a DDS or a StaticDDS.
                Allowed connections are a string of the form `channel X`.
        """
        conn = device.connection
        chan = int(conn.split('channel ')[-1])

        if isinstance(device, StaticDDS):
            if chan < self.dynamic_channels:
                raise LabscriptError(f'Channel {chan} configured as dynamic channel, can not create StaticDDS.')
            elif chan >= 4:
                raise LabscriptError('AD9959DDSSweeper only supports 4 channels')
        elif isinstance(device, DDS):
            if chan >= self.dynamic_channels:
                raise LabscriptError(f'Channel {chan} not configured as dynamic channel, can not create DDS.')

        super().add_device(device)

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
            raise LabscriptError(f'{device.description:s} {device.name:s} '+
                                 f'can only have frequencies between 0.0Hz and {self.dds_clock/2e6:.1f} MHz, ' + 
                                 f'the limit imposed by {self.name:s}.')

        # It's faster to add 0.5 then typecast than to round to integers first:
        data = np.array((self.freq_scale*data)+0.5,dtype='<u4')
        return data
        
    def quantise_phase(self, data, device):
        """Ensures phase is wrapped about 360 degrees and scales to instrument
        units before type casting to uint16."""
        if not isinstance(data, np.ndarray):
            data = np.array(data)
        # ensure that phase wraps around:
        data %= 360
        # It's faster to add 0.5 then typecast than to round to integers first:
        data = np.array((self.phase_scale*data)+0.5,dtype='<u2')
        return data
        
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
        data = np.array((self.amp_scale*data)+0.5,dtype='<u2')
        return data

    def generate_code(self, hdf5_file):

        dyn_DDSs = {}
        stat_DDSs = {}
        num_channels = len(self.child_devices)

        # later we will need something better to support the other modes
        if self.sweep_mode > 0:
            mode = 'sweeps'
        else:
            mode = 'steps'
        
        for output in self.child_devices:
            # Check that the instructions will fit into RAM:
            max_instructions = self.max_instructions_map[self.pico_board][mode][num_channels-1]
            max_instructions -= 2 # -2 to include space for dummy instructions
            if isinstance(output, DDS) and len(output.frequency.raw_output) > max_instructions:
                raise LabscriptError(
                                    f'{self.name} can only support {max_instructions} instructions. \
                                    Please decrease the sample rates of devices on the same clock, \
                                    or connect {self.name} to a different pseudoclock.')
            try:
                _, channel = output.connection.split()
                channel = int(channel)
                assert channel in range(4), 'requested channel out of range'
            except Exception:
                raise LabscriptError('%s %s has invalid connection string: \'%s\'. ' % (output.description,output.name,str(output.connection)) + 
                                     'Format must be \'channel n\' with n from 0 to 4.')
            
            # separate dynamic from static
            if isinstance(output, DDS):
                dyn_DDSs[channel] = output
            elif isinstance(output, StaticDDS):
                stat_DDSs[channel] = output

        # if no channels are being used, no need to continue
        if not dyn_DDSs and not stat_DDSs:
            return

        # Ensure data table is constructed in correct order
        if dyn_DDSs:
            dyn_DDSs = dict(sorted(dyn_DDSs.items()))
        if stat_DDSs:
            stat_DDSs = dict(sorted(stat_DDSs.items()))

        for connection in dyn_DDSs:
            dds = dyn_DDSs[connection]   
            dds.frequency.raw_output = self.quantise_freq(dds.frequency.raw_output, dds)
            dds.phase.raw_output = self.quantise_phase(dds.phase.raw_output, dds)
            dds.amplitude.raw_output = self.quantise_amp(dds.amplitude.raw_output, dds)

        dyn_dtypes = {'names':['%s%d' % (k, i) for i in dyn_DDSs for k in ['freq', 'amp', 'phase'] ],
                'formats':[f for i in dyn_DDSs for f in ('<u4', '<u2', '<u2')]}

        # TODO: may not be necessary, should be able to get length from dds.xxxx.raw_output size
        clockline = self.parent_clock_line
        pseudoclock = clockline.parent_device
        times = pseudoclock.times[clockline]

        dyn_table = np.zeros(len(times), dtype=dyn_dtypes)

        for i, dds in dyn_DDSs.items():
            dyn_table['freq%d' % i][:] = dds.frequency.raw_output
            dyn_table['amp%d' % i][:] = dds.amplitude.raw_output
            dyn_table['phase%d' % i][:] = dds.phase.raw_output

        static_dtypes = {
            'names':['%s%d' % (k, i) for i in stat_DDSs for k in ['freq', 'amp', 'phase'] ],
            'formats':[f for i in stat_DDSs for f in ('float', 'float', 'float')]
            }
        
        static_table = np.zeros(1, dtype=static_dtypes)

        for connection in stat_DDSs.keys():
            sdds = stat_DDSs[connection]
            static_table['freq%d' % connection] = sdds.frequency.raw_output[0]
            static_table['amp%d' % connection] = sdds.amplitude.raw_output[0]
            static_table['phase%d' % connection] = sdds.phase.raw_output[0]
        
        # write out data tables
        grp = self.init_device_group(hdf5_file)
        if dyn_DDSs:
            grp.create_dataset('dds_data', compression=config.compression, data=dyn_table)
        if stat_DDSs:
            grp.create_dataset('static_data', compression=config.compression, data=static_table)
        # Store parameter scale factors
        self.set_property('frequency_scale_factor', self.freq_scale, location='device_properties')
        self.set_property('amplitude_scale_factor', self.amp_scale, location='device_properties')
        self.set_property('phase_scale_factor', self.phase_scale, location='device_properties')
