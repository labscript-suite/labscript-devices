#####################################################################
#                                                                   #
# /naqslab_devices/SignalGenerator/BLACS/HP_8643A.py                #
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

class HP_8643ATab(SignalGeneratorTab):
    # Capabilities
    base_units = {'freq':'MHz', 'amp':'dBm'}
    base_min = {'freq':0.26,   'amp':-137}
    base_max = {'freq':1030,  'amp':13}
    base_step = {'freq':1,    'amp':0.1}
    base_decimals = {'freq':8, 'amp':2}
    # Event Status Byte Label Definitions for HP8643A
    status_byte_labels = {'bit 7':'Power On', 
                          'bit 6':'URQ',
                          'bit 5':'Command Error',
                          'bit 4':'Execution Error',
                          'bit 3':'Device Error',
                          'bit 2':'Query Error',
                          'bit 1':'RQC',
                          'bit 0':'Operation Complete'}
    
    def __init__(self,*args,**kwargs):
        self.device_worker_class = HP_8643AWorker
        SignalGeneratorTab.__init__(self,*args,**kwargs)      

class HP_8643AWorker(SignalGeneratorWorker):
    # define the scale factor
    # Writing: scale*desired_freq // Reading:desired_freq/scale
    scale_factor = 1.0e6
    amp_scale_factor = 1.0
    
    def init(self):
        '''Calls parent init and sends device specific initialization commands'''
        SignalGeneratorWorker.init(self)
        
        # enables ESR status reading
        self.connection.write('*ESE 60;*SRE 32;*CLS')
        self.esr_mask = 60
    
    # define instrument specific read and write strings for Freq & Amp control
    freq_write_string = 'FREQ:CW {:.2f} HZ'  #HP8643A has 0.01 Hz resolution, in Hz
    freq_query_string = 'FREQ:CW?' #HP8643A returns float, in Hz
    def freq_parser(self,freq_string):
        '''Frequency Query string parser for HP8643A
        freq_string format is float, in Hz
        Returns float in instrument units, Hz (i.e. needs scaling to base_units)'''
        return float(freq_string)
    amp_write_string = 'AMPL:LEV {:.2f} DBM' #HP8643A accepts two decimal, in dBm
    amp_query_string = 'AMPL:LEV?' #HP8643A returns float in dBm
    def amp_parser(self,amp_string):
        '''Amplitude Query string parser for HP8643A
        amp_string format is float in configured units (dBm by default)
        Returns float in instrument units, dBm'''
        return float(amp_string)
    enable_write_string = enable_on_off_formatter('AMPL:STAT {:s}')
    enable_query_string = 'AMPL:STAT?'
    def enable_parser(self,enable_string):
        '''Output Enable Query for HP 8643.'''
        return 'ON' in enable_string
        
    def check_status(self):
        # no real info in stb in these older sig gens, use esr instead
        esr = int(self.connection.query('*ESR?'))
        
        # if esr is non-zero, read out the error message and report
        # use mask to ignore non-error messages
        if (esr & self.esr_mask) != 0:
            err_string = self.connection.query('SYST:ERR? STR')
            # some error conditions do not persist to query
            # Still need to inform user of issue
            if err_string.endswith('0'):
                err_string = 'Event Status Register: {0:d}'.format(esr)
            
            msg = 'HP 8643A device {0:s} has \n{1:s}'
            raise LabscriptError(dedent(msg.format(self.VISA_name,err_string))) 
        
        # note: HP 8643A has 16 bits in ESR, 
        # so need to ensure future use bits not present when passed
        return self.convert_register(esr & 255)

