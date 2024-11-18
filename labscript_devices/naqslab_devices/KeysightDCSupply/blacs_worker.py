#####################################################################
#                                                                   #
# /naqslab_devices/KeysightDCSupply/blacs_worker.py                 #
#                                                                   #
# Copyright 2020, David Meyer                                       #
#                                                                   #
# This file is part of the naqslab devices extension to the         #
# labscript_suite. It is licensed under the Simplified BSD License. #
#                                                                   #
#                                                                   #
#####################################################################
import numpy as np

from naqslab_devices.VISA.blacs_worker import VISAWorker
from labscript import LabscriptError 

import labscript_utils.h5_lock, h5py

class KeysightDCSupplyWorker(VISAWorker):

    # define the status masks
    esr_mask = 60
    qsr_mask = 1539

    # define the initialisation string
    init_string = f'*ESE {esr_mask};STAT:QUES:ENAB {qsr_mask};*CLS'
    ident_string = 'E364'
    
    # define instrument specific read and write strings
    write_both_string = 'APPL %.5f, %.5f'
    write_volt_string = 'VOLT %.5f'
    write_current_string = 'CURR %.5f'
    read_string = 'APPL?'

    def read_parser(self,response):
        '''Parses the Voltage & Amplitude response string

        Args:
            response (str): Instrument response to current voltage/current query.
                            Has format of "d.ddddd, d.ddddd"

        Returns:
            (tuple): containing

                V (float): Current Voltage Setting
                A (float): Current Current Setting
        '''
        V, A = response[1:-3].split(',')
        return float(V), float(A) 
    
    def init(self):
        # Call the VISA init to initialise the VISA connection
        VISAWorker.init(self)

        response = self.connection.query('*IDN?')
        if self.ident_string not in response:
            msg = f'''KeysightDCSupply does not support:\t{response}'''
            raise LabscriptError(msg)

        self.connection.write(self.init_string)
        
        if self.limited == 'volt':
            self.write_string = self.write_volt_string
        else:
            self.write_string = self.write_current_string

        # set voltage range
        self.connection.write('VOLT:RANG '+self.range)
        
        # initialize the smart cache
        self.smart_cache = {'CURRENT_DATA': 
                                {'channel %d'%i:None for i in self.allowed_outputs}
                            }
    
    def check_remote_values(self):
        # Get the currently output values:
        results = {}
        
        # these query strings and parsers depend heavily on device
        for i in self.allowed_outputs:
            response = self.connection.query(self.read_string)
            V, A = self.read_parser(response)
            results['channel %d'%i] = V if self.limited == 'volt' else A

        return results
    
    def program_manual(self,front_panel_values):
        
        for output, val in front_panel_values.items():
            self.connection.write(self.write_string%(val))
            # invalidate smart cache after manual update
            self.smart_cache['CURRENT_DATA'][output] = None
        
        return self.check_remote_values()        

    def transition_to_buffered(self,device_name,h5file,initial_values,fresh):
        # call parent method to do basic preamble
        VISAWorker.transition_to_buffered(self,device_name,h5file,initial_values,fresh)
        data = None
        final_values = initial_values
        # Program static values
        with h5py.File(h5file,'r') as hdf5_file:
            group = hdf5_file['/devices/'+device_name]
            # If there are values to set the unbuffered outputs to, set them now:
            if 'STATIC_DATA' in group:
                data = group['STATIC_DATA'][:][0]
                
        if data is not None:
            if fresh or data != self.smart_cache['CURRENT_DATA']:
                
                # only program channels as needed
                channels = [int(name[-1]) for name in data.dtype.names]
                for i in channels:
                    if data[i] != self.smart_cache['CURRENT_DATA']['channel %d'%i]:
                        self.connection.write(self.write_string%(data[i]))
                        final_values['channel %d'%i] = data[i]
                        self.smart_cache['CURRENT_DATA']['channel %d'%i] = data[i]                
   
            else:
                final_values = self.initial_values
                
        return final_values

    def check_status(self):
        '''Customised check status for Keysight DC supplies.

        This method combines flags from the event status register and the
        questionable status register.'''

        response = self.connection.query_ascii_values('*ESR?;STAT:QUES?;QUES:COND?',separator=';')
        [esr, qsr, cond] = [int(i) for i in response]

        if (esr & self.esr_mask) != 0:
            err_list = []
            while True:
                err_string = self.connection.query('SYST:ERR?')
                err,description = err_string.split(',')
                if int(err) != 0:
                    err_list.append(err_string)
                else:
                    break
            msg = f'{self.VISA_name} has errors\n\t{err_list}'
            raise LabscriptError(dedent(msg))
        
        return self.merge_registers(esr,qsr,cond)

    def merge_registers(self, esr, qsr,cond):
        '''Merges the ESR & QSR registers with the condition into a hybrid register 
        and converts to a dictionary for display on the BLACStab.

        Args:
            esr (int): Value of the Event Status Register
            qsr (int): Value of the Questionable Status Register
            cond (int): Response of STATus:QUEStionable:CONDition?

        Returns:
            return_vals (dict): Dictionary of values from the esr and qsr registers.
        '''

        return_vals = self.convert_register(esr)
        # qsr register is more than 8 bits, so need to do convert_register by hand
        qsr_status = f'{qsr:11b}'[::-1]

        # note cond == 0 is output off/unregulated and cond == 3 is supply failure
        return_vals['bit 0'] = cond == 1
        return_vals['bit 1'] = cond == 2
        return_vals['bit 6'] = bool(int(qsr_status[9])) if qsr_status[9]!=' ' else False
        current_unregulated = bool(int(qsr_status[1])) if qsr_status[1]!=' ' else False
        volt_unregulated = bool(int(qsr_status[0])) if qsr_status[0]!=' ' else False
        return_vals['bit 7'] = current_unregulated | volt_unregulated

        return return_vals