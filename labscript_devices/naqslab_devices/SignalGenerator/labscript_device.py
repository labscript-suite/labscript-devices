#####################################################################
#                                                                   #
# /naqslab_devices/SignalGenerator/labscript_device.py             #
#                                                                   #
# Copyright 2018, David Meyer                                       #
#                                                                   #
# This file is part of the naqslab devices extension to the         #
# labscript_suite. It is licensed under the Simplified BSD License. #
#                                                                   #
#                                                                   #
#####################################################################
import numpy as np

from naqslab_devices.VISA.labscript_device import VISA
from labscript import LabscriptError, set_passed_properties, config
from labscript_utils import dedent

from naqslab_devices import StaticFreqAmp

__version__ = '0.2.0'
__author__ = ['dihm']

# note, when adding a new model, put the labscript_device inheritor class
# into Models.py and the BLACS classes into a file named for the device
# in the BLACS subfolder. Update register_classes.py and __init__.py
# accordingly.


class SignalGenerator(VISA):
    description = 'Signal Generator'
    allowed_children = [StaticFreqAmp]
    allowed_chans = [0]
    enabled_chans = []
    # define the scale factor - converts between BLACS front panel and instr
    # Writing: scale*desired_freq // Reading:desired_freq/scale
    scale_factor = 1.0e6 # ensure that the BLACS worker class has same scale_factor
    freq_limits = (0,1) # set in scaled unit
    amp_scale_factor = 1.0 # ensure that the BLACS worker class has same amp_scale_factor
    amp_limits = (0,1) # set in scaled unit

    @set_passed_properties()
    def __init__(self, name, VISA_name):
        '''VISA_name can be full VISA connection string or NI-MAX alias'''
        # Signal Generators do not have a parent device
        VISA.__init__(self,name,None,VISA_name)

    def quantise_freq(self,data, device):
        '''Quantize the frequency in units of Hz and check it's within bounds'''
        # It's faster to add 0.5 then typecast than to round to integers first (device is programmed in Hz):    
        data = np.array((self.scale_factor*data)+0.5, dtype=np.uint64)

        # Ensure that frequencies are within bounds:
        if any(data < self.freq_limits[0] )  or any(data > self.freq_limits[1] ):
            msg = '''{:s} {:s} can only have frequencies between 
                {:E}Hz and {:E}Hz, {} given'''.format(device.description, 
                                        device.name, *self.freq_limits,
                                        data)
            raise LabscriptError(dedent(msg))
        return data, self.scale_factor

    def quantise_amp(self,data, device):
        '''Quantize the amplitude in units of dBm and check it's within bounds'''
        # Keep as float since programming often done down to 0.1dBm (device is programmed in dBm):                       
        data = np.array((self.amp_scale_factor*data), dtype=np.float16)

        # Ensure that amplitudes are within bounds:        
        if any(data < self.amp_limits[0] )  or any(data > self.amp_limits[1] ):
            msg = '''{:s} {:s} can only have amplitudes between 
                {:.1f} dBm and {:.1f} dBm, {} given'''.format(device.description, 
                                                device.name,*self.amp_limits,
                                                data)
            raise LabscriptError(dedent(msg))
        return data, self.amp_scale_factor

    def enable_output(self, channel=0):
        """Enable the output at the device level.

        This is a software enable only, it cannot be hardware timed.

        Args:
            channel (int, optional): Channel to enable. Defaults to 0, which
                is expected for single output devices.
        """

        if channel in self.allowed_chans:
            if channel not in self.enabled_chans:
                self.enabled_chans.append(channel)
        else:
            raise LabscriptError(f'Channel {channel} is not a valid option for {self.device.name}')

    def generate_code(self, hdf5_file):
        if not len(self.child_devices):
            print(f'No outputs attached to {self.name:s}')
            return
        for output in self.child_devices:
            try:
                prefix, channel = output.connection.split()
                channel = int(channel)
            except:
                msg = '''{:s} {:s} has invalid connection string: \'{!s}\'.
                Format must be \'channel n\' with n equal 0.'''
                raise LabscriptError(dedent(msg.format(output.description,
                                            output.name,output.connection)))
            if channel != 0:
                msg = '''{:s} {:s} has invalid connection string: \'{!s}\'.
                Format must be \'channel n\' with n equal 0.'''
                raise LabscriptError(dedent(msg.format(output.description,
                                            output.name,output.connection)))
            dds = output
        # Call these functions to finalise stuff:
        ignore = dds.frequency.get_change_times()
        dds.frequency.make_timeseries([])
        dds.frequency.expand_timeseries()

        ignore = dds.amplitude.get_change_times()
        dds.amplitude.make_timeseries([])
        dds.amplitude.expand_timeseries()

        dds.frequency.raw_output, dds.frequency.scale_factor = self.quantise_freq(dds.frequency.raw_output, dds)
        dds.amplitude.raw_output, dds.amplitude.scale_factor = self.quantise_amp(dds.amplitude.raw_output, dds)
        static_dtypes = np.dtype({'names':['freq0','amp0','gate0'],'formats':[np.uint64,np.float16,bool]})
        static_table = np.zeros(1, dtype=static_dtypes)
        static_table['freq0'].fill(1)
        static_table['freq0'] = dds.frequency.raw_output[0]
        static_table['amp0'].fill(1)
        static_table['amp0'] = dds.amplitude.raw_output[0]
        static_table['gate0'].fill(0)
        static_table['gate0'] = 0 in self.enabled_chans # returns True if channel 0 enabled
        grp = hdf5_file.create_group('/devices/'+self.name)
        grp.create_dataset('STATIC_DATA',compression=config.compression,data=static_table) 
        self.set_property('frequency_scale_factor', self.scale_factor, location='device_properties')
        self.set_property('amplitude_scale_factor', self.amp_scale_factor, location='device_properties')

