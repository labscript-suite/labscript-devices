#####################################################################
#                                                                   #
# /naqslab_devices/SignalGenerator/BLACS/RS_SMHU.py                 #
#                                                                   #
# Copyright 2018, David Meyer                                       #
#                                                                   #
# This file is part of the naqslab devices extension to the         #
# labscript_suite. It is licensed under the Simplified BSD License. #
#                                                                   #
#                                                                   #
#####################################################################
from naqslab_devices.SignalGenerator.blacs_tab import SignalGeneratorTab
from naqslab_devices.SignalGenerator.blacs_worker import SignalGeneratorWorker, enable_on_off_formatter
from labscript import LabscriptError
from labscript_utils import dedent


class RS_SMHUTab(SignalGeneratorTab):
    # Capabilities
    base_units = {'freq':'MHz', 'amp':'dBm'}
    base_min = {'freq':0.1,   'amp':-140}
    base_max = {'freq':4320,  'amp':13}
    base_step = {'freq':1,    'amp':0.1}
    base_decimals = {'freq':7, 'amp':1}
    # Event Byte Label Definitions for RS SMHU
    status_byte_labels = {'bit 7':'Power On', 
                          'bit 6':'URQ',
                          'bit 5':'Command Error',
                          'bit 4':'Execution Error',
                          'bit 3':'Device-Dependent Error',
                          'bit 2':'Query Error',
                          'bit 1':'SRQ',
                          'bit 0':'OPC'}
    
    def __init__(self,*args,**kwargs):
        self.device_worker_class = RS_SMHUWorker
        SignalGeneratorTab.__init__(self,*args,**kwargs)      


class RS_SMHUWorker(SignalGeneratorWorker):
    # define the scale factor
    # Writing: scale*desired_freq // Reading:desired_freq/scale
    scale_factor = 1.0e6
    amp_scale_factor = 1.0
    
    def init(self):
        '''Calls parent init and sends device specific initialization commands'''
        SignalGeneratorWorker.init(self)
        
        # enables ESR status reading
        try:
            # this is first command to device, 
            # if failure then it probably isn't connected
            self.connection.write('HEADER:OFF;*ESE 60;*SRE 32;*CLS')
        except:
            msg = 'Initial command to %s did not succeed. Is it connected?'   
            raise LabscriptError(dedent(msg%self.VISA_name)) from None
        self.esr_mask = 60
    
    # define instrument specific read and write strings for Freq & Amp control
    freq_write_string = 'RF {:.1f}HZ' 
    freq_query_string = 'RF?'
    def freq_parser(self,freq_string):
        '''Frequency Query string parser for RS SMHU
        freq_string format is sdddddddddd.d
        Returns float in instrument units, Hz (i.e. needs scaling to base_units)'''
        return float(freq_string)
    amp_write_string = 'LEVEL:RF {:.1f}DBM'
    amp_query_string = 'LEVEL:RF?'
    def amp_parser(self,amp_string):
        '''Amplitude Query string parser for RS SMHU
        amp_string format is sddd.d
        Returns float in instrument units, dBm'''
        if amp_string == '\n':
            raise LabscriptError('RS SMHU device {0:s} has RF OFF!'.format(self.VISA_name))
        return float(amp_string)
    enable_write_string = enable_on_off_formatter('LEV:RF {:s}')
    enable_query_string = 'LEV:RF?'
    def enable_parser(self,enable_string):
        '''Output Enable Query for RS SMHU.'''
        return 'ON' in enable_string
            
    def check_status(self):
        # no real info in stb in these older sig gens, use esr instead
        esr = int(self.connection.query('*ESR?'))
        
        # if esr is non-zero, read out the error message and report
        # use mask to ignore non-error messages
        if (esr & self.esr_mask) != 0:
            err_string = self.connection.query('ERRORS?')
            # some error conditions do not persist to ERRORS? query (ie query errors)
            # Still need to inform user of issue
            if err_string.endswith('0'):
                err_string = 'Event Status Register: {0:d}'.format(esr)
            else:
                raise LabscriptError('RS SMHU device {0:s} has \n{1:s}'.format(self.VISA_name,err_string)) 
        
        # note: SMHU has 9 bits in ESR, 
        # so need to ensure last bit (Sweep End) not present when passed
        return self.convert_register(esr & 255)

