#####################################################################
#                                                                   #
# /naqslab_devices/SignalGenerator/BLACS/RS_SMA100B.py              #
#                                                                   #
# Copyright 2019, David Meyer                                       #
#                                                                   #
# This file is part of the naqslab devices extension to the         #
# labscript_suite. It is licensed under the Simplified BSD License. #
#                                                                   #
#                                                                   #
#####################################################################
from naqslab_devices.SignalGenerator.blacs_tab import SignalGeneratorTab
from naqslab_devices.SignalGenerator.blacs_worker import SignalGeneratorWorker
from labscript import LabscriptError      


class RS_SMA100BTab(SignalGeneratorTab):
    # Capabilities
    base_units = {'freq':'GHz', 'amp':'dBm'}
    base_min = {'freq':8e-6,   'amp':-145}
    base_max = {'freq':20,  'amp':35} # only 30 if f<=1 MHz
    base_step = {'freq':0.1,    'amp':1}
    base_decimals = {'freq':9, 'amp':2}
    # Status Byte Label Definitions for SMA100B
    status_byte_labels = {'bit 7':'Operation',
                          'bit 6':'SRQ',
                          'bit 5':'ESB',
                          'bit 4':'Message Available',
                          'bit 3':'Questionable Status',
                          'bit 2':'Error Queue Not Empty',
                          'bit 1':'Unused',
                          'bit 0':'Unused'}

    def __init__(self,*args,**kwargs):
        self.device_worker_class = RS_SMA100BWorker
        SignalGeneratorTab.__init__(self,*args,**kwargs)


class RS_SMA100BWorker(SignalGeneratorWorker):
    # define the scale factor
    # Writing: scale*desired_freq // Reading:desired_freq/scale
    scale_factor = 1.0e9
    amp_scale_factor = 1.0
    
    # define instrument specific read and write strings for Freq & Amp control
    freq_write_string = 'FREQ:CW {:.0f}HZ'
    freq_query_string = 'FREQ:CW?' # SMA100B returns 'ddddddddddd', in Hz
    def freq_parser(self,freq_string):
        '''Frequency Query string parser for SMF100B
        freq_string format is ddddddddddd
        Returns float in instrument units, Hz (i.e. needs scaling to base_units)'''
        return float(freq_string)
    amp_write_string = 'POW:POW {:.2f}dBm' # SMA100B accepts two decimals, in dBm
    amp_query_string = 'POW?' # SMA100B returns 'sdd.dd'
    def amp_parser(self,amp_string):
        '''Amplitude Query string parser for SMF100B
        Returns float in instrument units, dBm'''
        return float(amp_string)
    enable_write_string = 'OUTP:STAT {:d}' # take a bool value
    enable_query_string = 'OUTP:STAT?' # returns 0 or 1
        
    def check_status(self):
        # call parent method to read status byte register
        results = SignalGeneratorWorker.check_status(self)
        # do some device specific error handling with status byte information
        if results['bit 2'] == True:
            errors = self.connection.query('SYST:ERR:ALL?')
            raise LabscriptError('SMA100B VISA device {:s} has Errors in Queue: \n{:s}'.format(self.VISA_name,errors))
            
        return results
