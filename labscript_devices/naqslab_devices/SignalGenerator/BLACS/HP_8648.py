#####################################################################
#                                                                   #
# /naqslab_devices/SignalGenerator/BLACS/HP_8648.py                 #
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

class HP_8648ATab(SignalGeneratorTab):
    # Capabilities
    base_units = {'freq':'MHz', 'amp':'dBm'}
    base_min = {'freq':0.1,   'amp':-136}
    base_max = {'freq':1000,  'amp':20}#max output depends on options/frequency
    base_step = {'freq':1,    'amp':1}
    base_decimals = {'freq':9, 'amp':1}
    # Event Status Byte Label Definitions for HP8648
    status_byte_labels = {'bit 7':'Power On', 
                          'bit 6':'URQ',
                          'bit 5':'Command Error',
                          'bit 4':'Execution Error',
                          'bit 3':'Device Error',
                          'bit 2':'Query Error',
                          'bit 1':'RQC',
                          'bit 0':'Operation Complete'}
    
    def __init__(self,*args,**kwargs):
        self.device_worker_class = HP_8648Worker
        SignalGeneratorTab.__init__(self,*args,**kwargs) 
        
class HP_8648BTab(HP_8648ATab):
    # Capabilities
    base_min = {'freq':0.009,   'amp':-136}
    base_max = {'freq':2000,  'amp':20}#max output depends on options/frequency
    
class HP_8648CTab(HP_8648ATab):
    # Capabilities
    base_min = {'freq':0.009,   'amp':-136}
    base_max = {'freq':3200,  'amp':20}#max output depends on options/frequency
    
class HP_8648DTab(HP_8648ATab):
    # Capabilities
    base_min = {'freq':0.009,   'amp':-136}
    base_max = {'freq':4000,  'amp':20}#max output depends on options/frequency

class HP_8648Worker(SignalGeneratorWorker):
    # define the scale factor
    # Writing: scale*desired_freq // Reading:desired_freq/scale
    scale_factor = 1.0e6
    amp_scale_factor = 1.0
    
    def init(self):
        '''Calls parent init and sends device specific initialization commands'''        
        SignalGeneratorWorker.init(self)
        try:
            ident_string = self.connection.query('*IDN?')
        except:
            msg = '\'*IDN?\' command did not complete. Is %s connected?'
            raise LabscriptError(dedent(msg%self.VISA_name)) from None
        
        if '8648' not in ident_string:
            msg = '%s is not supported by the HP_8648 class.'
            raise LabscriptError(dedent(msg%ident_string))
        
        # enables ESR status reading
        self.connection.write('*ESE 60;*SRE 32;*CLS')
        self.esr_mask = 60
    
    # define instrument specific read and write strings for Freq & Amp control
    # Note that insturment display does not have as much resolution as device
    freq_write_string = 'FREQ:CW {:.3f} HZ' #HP8648 has 0.001 Hz resolution, in Hz
    freq_query_string = 'FREQ:CW?' #HP8648 returns float, in Hz
    def freq_parser(self,freq_string):
        '''Frequency Query string parser for HP8648
        freq_string format is float, in Hz
        Returns float in instrument units, Hz (i.e. needs scaling to base_units)'''
        return float(freq_string)
    amp_write_string = 'POW:AMPL {:.1f} DBM' #HP8648 accepts one decimal, in dBm
    amp_query_string = 'POW:AMPL?' #HP8648 returns float in dBm
    def amp_parser(self,amp_string):
        '''Amplitude Query string parser for HP8648
        amp_string format is float in configured units (dBm by default)
        Returns float in instrument units, dBm'''
        return float(amp_string)
    enable_write_string = enable_on_off_formatter('OUTP:STAT {:s}')
    enable_query_string = 'OUTP:STAT?'
    def enable_parser(self,enable_string):
        '''Output Enable Query for HP 8648.'''
        return 'ON' in enable_string
        
    def check_status(self):
        # no real info in stb in these older sig gens, use esr instead
        esr = int(self.connection.query('*ESR?'))
        
        # if esr is non-zero, read out the error message and report
        # use mask to ignore non-error messages
        if (esr & self.esr_mask) != 0:
            err_string = self.connection.query('SYST:ERR?')
            # some error conditions do not persist to query
            # Still need to inform user of issue
            if 'No error' in err_string:
                err_string = 'Event Status Register: {0:d}'.format(esr)

            msg = '{0:s} has \n{1:s}'
            raise LabscriptError(dedent(msg.format(self.VISA_name,err_string))) 
        
        return self.convert_register(esr)

