#####################################################################
#                                                                   #
# /naqslab_devices/SignalGenerator/BLACS/KeysightSigGens.py         #
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

from labscript_utils import check_version, dedent
from labscript import LabscriptError

# need this version to ensure labscript device properties are auto-passed to worker
check_version('blacs','2.8.0','4')


class KeysightSigGenTab(SignalGeneratorTab):
    """BLACS Tab for Modern Keysight/Agilent/HP CW Signal Generators

    Specific devices should subclass this class and define 
    `base_units`
    `base_min`
    `base_max`
    `base_step`
    `base_decimals`
    for the frequency output 'channel 0'. Definitions are given is the base units.
    """
    # Event Status Byte Label Definitions for Keysight Sig Gens
    status_byte_labels = {'bit 7':'Power On', 
                          'bit 6':'URQ',
                          'bit 5':'Command Error',
                          'bit 4':'Execution Error',
                          'bit 3':'Device Error',
                          'bit 2':'Query Error',
                          'bit 1':'RQC',
                          'bit 0':'Operation Complete'}

    def __init__(self,*args,**kwargs):
        self.device_worker_class = KeysightSigGenWorker
        SignalGeneratorTab.__init__(self,*args,**kwargs)


class E8257NTab(KeysightSigGenTab):
    # Capabilities
    base_units = {'freq':'GHz', 'amp':'dBm'}
    base_min = {'freq':0.010,   'amp':-105}
    base_max = {'freq':40.0,  'amp':20}#max output depends on options/frequency
    base_step = {'freq':1,    'amp':1}
    base_decimals = {'freq':12, 'amp':1}


class KeysightSigGenWorker(SignalGeneratorWorker):
    """Generic BLACS worker for Modern Keysight/Agilent/HP CW Signal Generators

    This class defines the common frequency/amplitude read/write commands as well
    as general device configuration and communication. It uses the ESR byte
    instead of the standard STB byte for intstrument communications.

    The `scale_factor` and `amp_scale_factor` are taken from the labscript
    device specification.

    """
    # scale factors defined in labscript device specification
    # Writing: scale*desired_freq // Reading:desired_freq/scale
    
    def init(self):
        '''Calls parent init and sends device specific initialization commands'''        
        SignalGeneratorWorker.init(self)
        try:
            ident_string = self.connection.query('*IDN?')
        except:
            msg = '\'*IDN?\' command did not complete. Is %s connected?'
            raise LabscriptError(dedent(msg%self.VISA_name)) from None
        
        # log which device connected to worker terminal
        print('Connected to \n',ident_string)
        
        # enables ESR status reading
        self.connection.write('*ESE 60;*SRE 32;*CLS')
        self.esr_mask = 60
    
    # define instrument specific read and write strings for Freq & Amp control
    # Note that insturment display does not have as much resolution as device
    freq_write_string = 'FREQ:CW {:.3f} HZ' #assume 0.001 Hz resolution, in Hz
    freq_query_string = 'FREQ:CW?' # returns float, in Hz
    def freq_parser(self,freq_string):
        '''Frequency Query string parser for Keysight Sig Gens
        freq_string format is float, in Hz
        Returns float in instrument units, Hz (i.e. needs scaling to base_units)'''
        return float(freq_string)
    amp_write_string = 'POW:AMPL {:.1f} DBM' #assume accepts one decimal, in dBm
    amp_query_string = 'POW:AMPL?' #returns float in dBm
    def amp_parser(self,amp_string):
        '''Amplitude Query string parser for Keysight Sig Gens
        amp_string format is float in configured units (dBm by default)
        Returns float in instrument units, dBm'''
        return float(amp_string)
    enable_write_string = 'OUTP:STAT {:d}'
    enable_query_string = 'OUTP:STAT?'
        
    def check_status(self):
        # no real info in stb use esr instead
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

