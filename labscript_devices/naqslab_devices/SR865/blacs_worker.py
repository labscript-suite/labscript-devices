#####################################################################
#                                                                   #
# /naqslab_devices/SR865/blacs_worker.py                            #
#                                                                   #
# Copyright 2018, David Meyer                                       #
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

# import sensitivity and tau settings from labscript device
from naqslab_devices.SR865.labscript_device import sens, tau

class SR865Worker(VISAWorker):
    program_string = 'OFLT {:d};SCAL {:d};PHAS {:.6f}'
    read_string = 'OFLT?;SCAL?;PHAS?'   
    
    def phase_parser(self,phase_string):
        '''Phase Query string parser'''
        phase = float(phase_string)
        return phase
        
    def coerce_tau(self,tau_constant):
        '''Returns coerced, valid integer setting. 
        Tau value rounds up.
        Returns max or min valid setting if out of bound.'''
        coerced_i = int(np.digitize(tau_constant,tau,right=True))
        if coerced_i >= len(tau):
            coerced_i -= 1
        return coerced_i
        
    def coerce_sens(self,sensitivity):
        '''Returns coerced, valid integer setting. 
        Sens value rounds down.
        Returns max or min valid setting if out of bound.'''
        coerced_i = int(np.digitize(sensitivity,sens))
        if coerced_i >= len(sens):
            coerced_i -= 1
        return coerced_i
    
    def init(self):
        # Call the VISA init to initialise the VISA connection
        VISAWorker.init(self)
        
        # initial configure of the instrument
        self.connection.write('*ESE 122;*CLS;')
    
    def check_remote_values(self):
        '''Queries the current settings for all three parameters.
        Parses results to actual numbers and returns.'''
        results = {}

        [tau_i, sens_i, phase] = self.connection.query_ascii_values(self.read_string,separator=';')
            
        # convert to proper numbers
        results['tau'] = tau[int(tau_i)]
        results['sens'] = sens[int(sens_i)]
        results['phase'] = self.phase_parser(phase)

        return results
    
    def program_manual(self,front_panel_values):
        '''Performans manual updates from BLACS front panel.
        Tau and Sensitivity settings are coerced to nearest allowed value'''
        tau_i = self.coerce_tau(front_panel_values['tau'])
        sens_i = self.coerce_sens(front_panel_values['sens'])
        phase = front_panel_values['phase']
        
        self.connection.write(self.program_string.format(tau_i,sens_i,phase))
                
        return self.check_remote_values()        

    def transition_to_buffered(self,device_name,h5file,initial_values,fresh):
        # call parent method to do basic preamble
        VISAWorker.transition_to_buffered(self,device_name,h5file,initial_values,fresh)
        
        data = None
        with h5py.File(h5file,'r') as hdf5_file:
            group = hdf5_file['/devices/'+device_name]
            # If there are values to set the unbuffered outputs to, set them now:
            if 'STATIC_DATA' in group:
                data = group['STATIC_DATA'][:][0]
                
        # Save these values into final_values so the GUI can
        # be updated at the end of the run to reflect them:
        # assume initial values in case something isn't programmed
        self.final_values = initial_values
        
        if data is not None:
            # since static instrument, smart_cache replaced with initial vals
            cur = self.initial_values               
            if (data['tau_i'] != -1) and (fresh or (data['tau'] != cur['tau'])):
                self.connection.write('OFLT {:d}'.format(data['tau_i']))
                self.final_values['tau'] = tau[data['tau_i']]
            else:
                self.final_values['tau'] = initial_values['tau']
            if (data['sens_i'] != -1) and (fresh or (data['tau'] != cur['tau'])):
                self.connection.write('SCAL {:d}'.format(data['sens_i']))
                self.final_values['sens'] = sens[data['sens_i']]
            else:
                self.final_values['sens'] = initial_values['sens']
            if not np.isnan(data['phase']) and (fresh or (data['phase'] != cur['phase'])):
                self.connection.write('PHAS {:.6f}'.format(data['phase']))
                self.final_values['phase'] = data['phase']
            else:
                self.final_values['phase'] = initial_values['phase']
                    
        # write the final_values to h5file for later lookup
        with h5py.File(h5file, 'r+') as hdf5_file:
            group = hdf5_file['/devices/'+device_name]
            group.attrs.create('sensitivity',self.final_values['sens'])
            group.attrs.create('tau',self.final_values['tau'])
            group.attrs.create('phase',round(self.final_values['phase'],6))
                
        return self.final_values
        
    def check_status(self):
        '''Queries device state using the ESR register.
        Bit definitions defined in blacs_tab'''
        esr = int(self.connection.query('*ESR?'))
        mask = 122
        error_code = esr & mask
        
        if error_code:
            # error exists, but nothing to report beyond register value
            print('{:s} has ESR = {:d}'.format(self.VISA_name,error_code))
        
        return self.convert_register(esr)

