#####################################################################
#                                                                   #
# /naqslab_devices/TektronixTDS/blacs_worker.py                     #
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


class TDS_ScopeWorker(VISAWorker):   
    # define instrument specific read and write strings
    setup_string = ':HEADER OFF;*ESE 60;*SRE 32;*CLS;:DAT:ENC RIB;WID 2;'
    read_y_parameters_string = ':DAT:SOU CH%d;:WFMPRE:YZE?;YMU?;YOFF?'
    read_x_parameters_string = ':WFMPRE:XZE?;XIN?'
    read_waveform_string = 'CURV?'
    
    def waveform_parser(self,raw_waveform_array,y0,dy,yoffset):
        '''Parses the numpy array from the CURV? query.'''
        return (raw_waveform_array - yoffset)*dy + y0
    
    def init(self):
        
        # Call the VISA init to initialise the VISA connection
        VISAWorker.init(self)
        # Override the timeout for longer scope waits
        self.connection.timeout = 10000
        
        # Query device name to ensure supported scope
        ident_string = self.connection.query('*IDN?')
        if ('TEKTRONIX,TDS 2' in ident_string) or ('TEKTRONIX,TDS 1' in ident_string):
            # Scope supported!
            pass
        else:
            raise LabscriptError('Device {0:s} with VISA name {1:s} not supported!'.format(ident_string,self.VISA_name))  
        
        # initialization stuff
        self.connection.write(self.setup_string)
            
    def transition_to_manual(self,abort = False):
        if not abort:         
            with h5py.File(self.h5_file,'r') as hdf5_file:
                try:
                    # get acquisitions table values so we can close the file
                    acquisitions = hdf5_file['/devices/'+self.device_name+'/ACQUISITIONS'].value
                    trigger_time = hdf5_file['/devices/'+self.device_name+'/ACQUISITIONS'].attrs['trigger_time']
                except:
                    # No acquisitions!
                    return True
            # close lock on h5 to read from scope, it takes a while            
            data = {}
            for connection,label in acquisitions:
                channel_num = int(connection.split(' ')[-1])
                [y0,dy,yoffset] = self.connection.query_ascii_values(self.read_y_parameters_string % channel_num, container=np.array, separator=';')
                raw_data = self.connection.query_binary_values(self.read_waveform_string,
                datatype='h', is_big_endian=True, container=np.array)
                data[connection] = self.waveform_parser(raw_data,y0,dy,yoffset)
            # Need to calculate the time array
            num_points = len(raw_data)
            # read out the time parameters once outside the loop to save time
            [t0, dt] = self.connection.query_ascii_values(self.read_x_parameters_string,
                container=np.array, separator=';')
            data['time'] = np.arange(0,num_points,1,dtype=np.float64)*dt + t0
            # define the dtypes for the h5 arrays
            dtypes = np.dtype({'names':['t','values'],'formats':[np.float64,np.float32]})         
            
            # re-open lock on h5file to save data
            with h5py.File(self.h5_file,'r+') as hdf5_file:
                try:
                    measurements = hdf5_file['/data/traces']
                except:
                    # Group doesn't exist yet, create it
                    measurements = hdf5_file.create_group('/data/traces')
                # write out the data to the h5file
                for connection,label in acquisitions:
                    values = np.empty(num_points,dtype=dtypes)
                    values['t'] = data['time']
                    values['values'] = data[connection]
                    measurements.create_dataset(label, data=values)
                    # and save some timing info for reference to labscript time
                    measurements[label].attrs['trigger_time'] = trigger_time
            
            
        return True
        
    def check_status(self):
        '''Uses the more informative ESR register.'''
        esr = int(self.connection.query('*ESR?'))
        
        # if esr is non-zero, read out the error message and report
        if esr != 0:
            errors = self.connection.query('ALLEV?')
            raise LabscriptError('Tek Scope VISA device {0:s} has Errors in Queue: \n{1:s}'.format(self.VISA_name,errors))
            
        return self.convert_register(esr)

