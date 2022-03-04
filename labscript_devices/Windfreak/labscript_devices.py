#####################################################################
#                                                                   #
# /labscript_devices/Windfreak/labscript_devices.py                 #
#                                                                   #
# Copyright 2022, Monash University and contributors                #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

from labscript import LabscriptError, set_passed_properties, config, StaticDDS, IntermediateDevice, Device
from labscript_utils import dedent
from labscript_utils.unitconversions.generic_frequency import FreqConversion

import numpy as np


class WindfreakSynth(Device):
    description = 'Windfreak HDPro Synthesizer'
    allowed_children = [StaticDDS]
    # note, box labels 'A', 'B' map to programming channels 0, 1
    allowed_chans = [0, 1]
    enabled_chans = []

    # define output limitations for the SynthHDPro
    freq_limits = (10e6, 24e9)  # set in Hz
    freq_res = 1  # number of sig digits after decimal
    amp_limits = (-40.0, 20.0)  # set in dBm
    amp_res = 2
    phase_limits = (0.0, 360.0)  # in deg
    phase_res = 2

    @set_passed_properties(property_names={
        'connection_table_properties': [
            'com_port',
            'allowed_chans',
            'freq_limits',
            'freq_res',
            'amp_limits',
            'amp_res',
            'phase_limits',
            'phase_res',
            'trigger_mode',
        ]
    })
    def __init__(self, name, com_port="", trigger_mode='disabled', **kwargs):
        """Creates a Windfreak HDPro Synthesizer

        Args:
            name (str): python variable name to assign the device to.
            com_port (str): COM port connection string.
                Must take the form of 'COM d', where d is an integer.
            trigger_mode (str): Trigger mode for the device to use.
                Currently, labscript only directly programs 'rf enable',
                via setting DDS gates.
                labscript could correctly program other modes with some effort.
                Other modes can be correctly programmed externally,
                with the settings saved to EEPROM.
                **kwargs: Keyword arguments passed to :obj:`labscript:labscript.Device.__init__`.
        """

        Device.__init__(self, name, None, com_port, **kwargs)
        self.BLACS_connection = com_port
        self.trigger_mode = trigger_mode

    def add_device(self, device):
        Device.add_device(self, device)
        # ensure a valid default value
        device.frequency.default_value = 10e6

    def get_default_unit_conversion_classes(self, device):
        """Child devices call this during their `__init__` to get default unit conversions.

        If user has not overridden, will use generic FreqConversion class.        
        """

        return FreqConversion, None, None

    def validate_data(self, data, limits, device):
        """Tests that requested data is within limits.

        Args:
            data (iterable or numeric): Data to be checked.
                Input is cast to a numpy array of type float64.
            limits (tuple): 2-element tuple of (min, max) range
            device (:obj:`labscript:labscript.Device`): labscript device we are performing check on.

        Returns:
            numpy.ndarray: Input data, cast to a numpy array.
        """
        if not isinstance(data, np.ndarray):
            data = np.array(data,dtype=np.float64)
        if np.any(data < limits[0]) or np.any(data > limits[1]):
            msg = f'''{device.description} {device.name} can only have frequencies between
            {limits[0]:E}Hz and {limits[1]:E}Hz, {data} given
            '''
            raise LabscriptError(dedent(msg))
        return data

    def generate_code(self, hdf5_file):
        DDSs = {}

        for output in self.child_devices:

            try:
                prefix, channel = output.connection.split()
                if channel not in self.allowed_chans:
                    LabscriptError(f"Channel {channel} must be 0 or 0")
            except:
                msg = f"""{output.description}:{output.name} has invalid connection string.
                Only 'channel 0' or 'channel 1' is allowed.
                """
                raise LabscriptError(dedent(msg))

            DDSs[channel] = output

        for connection in DDSs:
            dds = DDSs[connection]
            dds.frequency.raw_output = self.validate_data(dds.frequency.static_value,self.freq_limits,dds)
            dds.amplitude.raw_output = self.validate_data(dds.amplitude.static_value,self.amp_limits,dds)
            dds.phase.raw_output = self.validate_data(dds.phase.static_value,self.phase_limits,dds)

        static_dtypes = [(f'freq{i:d}',np.float64) for i in self.allowed_chans] +\
                        [(f'amp{i:d}',np.float64) for i in self.allowed_chans] +\
                        [(f'phase{i:d}',np.float64) for i in self.allowed_chans] +\
                        [(f'gate{i:d}',bool) for i in self.allowed_chans]
        static_table = np.zeros(1,dtype=static_dtypes)

        for connection in DDSs:
            static_table[f'freq{connection}'] = dds.frequency.raw_output
            static_table[f'amp{connection}'] = dds.amplitude.raw_output
            static_table[f'phase{connection}'] = dds.phase.raw_output
            static_table[f'gate{connection}'] = connection in self.enabled_chans

        grp = self.init_device_group(hdf5_file)
        grp.create_dataset('STATIC_DATA',compression=config.compression,data=static_table)

    def enable_output(self, channel):
        """Enable an output channel at the device level.

        This is a software enable only, it cannot be hardware timed.

        Args:
            channel (int): Channel to enable.
        """

        if channel in self.allowed_chans:
            if channel not in self.enabled_chans:
                self.enabled_chans.append(channel)
        else:
            raise LabscriptError(f'Channel {channel} is not a valid option for {self.device.name}.')
