#####################################################################
#                                                                   #
# /naqslab_devices/SignalGenerator/BLACS/HP_8642A.py                #
#                                                                   #
# Copyright 2018, David Meyer                                       #
#                                                                   #
# This file is part of the naqslab devices extension to the         #
# labscript_suite. It is licensed under the Simplified BSD License. #
#                                                                   #
#                                                                   #
#####################################################################
from naqslab_devices.SignalGenerator.blacs_tab import SignalGeneratorTab
from naqslab_devices.SignalGenerator.blacs_worker import SignalGeneratorWorker
from labscript import LabscriptError
import numpy as np


class enable_on_off_formatter(str):
    '''Class overload that converts input bools to ON or OFF string'''

    def format(self, state):
        if state == 0:
            s = 'OF'
        elif state == 1:
            s = 'ON'
        else:
            raise ValueError('Argument must be 0 or 1 equivalent.')

        return super().format(s)

class HP_8642ATab(SignalGeneratorTab):
    # Capabilities
    base_units = {'freq':'MHz', 'amp':'dBm'}
    base_min = {'freq':0.1,   'amp':-140}
    base_max = {'freq':1057.5,  'amp':20}
    base_step = {'freq':1,    'amp':0.1}
    base_decimals = {'freq':6, 'amp':1}
    # Status Byte Label Definitions for HP8642A
    status_byte_labels = {'bit 7':'Parameter Changed', 
                          'bit 6':'RQS',
                          'bit 5':'Error',
                          'bit 4':'Ready',
                          'bit 3':'Local/Remote',
                          'bit 2':'Execution Error',
                          'bit 1':'Hardware Error',
                          'bit 0':'End of Sweep'}
    
    def __init__(self,*args,**kwargs):
        self.device_worker_class = HP_8642AWorker
        SignalGeneratorTab.__init__(self,*args,**kwargs)      

class HP_8642AWorker(SignalGeneratorWorker):
    # define the scale factor
    # Writing: scale*desired_freq // Reading:desired_freq/scale
    scale_factor = 1.0e6
    amp_scale_factor = 1.0
    
    # define instrument specific read and write strings for Freq & Amp control
    freq_write_string = 'FR {:.0f} HZ'  #HP8642A can only accept 10 digits, in Hz
    freq_query_string = 'FROA' #HP8642A returns 'FR sdddddddddd.0 HZ', in Hz
    def freq_parser(self,freq_string):
        '''Frequency Query string parser for HP8642A
        freq_string format is FR sdddddddddd.0 HZ
        Returns float in instrument units, Hz (i.e. needs scaling to base_units)'''
        return float(freq_string.split()[1])
    amp_write_string = 'AP {:.1f} DM' #HP8642A accepts one decimal, in dBm
    amp_query_string = 'APOA' #HP8642A returns 'AP sddd.d DM'
    def amp_parser(self,amp_string):
        '''Amplitude Query string parser for HP8642A
        amp_string format is AP sddd.d DM
        Returns float in instrument units, dBm'''
        # values less than -200 indicate instrument errors 
        # -201: RF OFF
        # -202: reverse power is tripped
        amp = float(amp_string.split()[1])
        if amp == -201:
            return np.nan
        elif amp <= -200:
            raise LabscriptError('HP8642A error code {:d} for VISA device: {:s}'.format(amp,self.VISA_name))
        else:
            # No error on amp read
            return amp
    enable_write_string = enable_on_off_formatter('AP{:s}')
    enable_query_string = 'APOA'
    def enable_parser(self, enable_string):
        '''Query output status by checking for error codes.'''
        amp = float(enable_string.split()[1])
        if amp == -201:
            return False
        elif amp <= -200:
            raise LabscriptError('HP8642A error code {:d} for VISA device: {:s}'.format(amp,self.VISA_name))
        else:
            # No error on amp read, output enabled
            return True