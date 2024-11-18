#####################################################################
#                                                                   #
# /naqslab_devices/TektronixTDS/labscript_device.py                 #
#                                                                   #
# Copyright 2018, David Meyer                                       #
#                                                                   #
# This file is part of the naqslab devices extension to the         #
# labscript_suite. It is licensed under the Simplified BSD License. #
#                                                                   #
#                                                                   #
#####################################################################
from labscript import TriggerableDevice, config, LabscriptError, set_passed_properties
from naqslab_devices import ScopeChannel

__version__ = '0.1.0'
__author__ = ['dihm']
                   
class TDS_Scope(TriggerableDevice):
    description = 'Tektronics TDS Series Digital Oscilliscope'
    allowed_children = [ScopeChannel]
    trigger_duration = 1e-3
    
    @set_passed_properties(property_names = {
        "device_properties":["VISA_name"]}
        )
    def __init__(self, name,VISA_name, trigger_device, trigger_connection, **kwargs):
        '''VISA_name can be full VISA connection string or NI-MAX alias.
        Trigger Device should be fast clocked device. '''
        self.VISA_name = VISA_name
        self.BLACS_connection = VISA_name
        TriggerableDevice.__init__(self,name,trigger_device,trigger_connection,**kwargs)
        
        # initialize start_time variable
        self.trigger_time = None
        
        
    def generate_code(self, hdf5_file):
            
        Device.generate_code(self, hdf5_file)
        
        acquisitions = []
        for channel in self.child_devices:
            if channel.acquisitions:
                acquisitions.append((channel.connection,channel.acquisitions[0]['label']))
        acquisition_table_dtypes = np.dtype({'names':['connection','label'],'formats':['a256','a256']})
        acquisition_table = np.empty(len(acquisitions),dtype=acquisition_table_dtypes)
        for i, acq in enumerate(acquisitions):
            acquisition_table[i] = acq   
        
        grp = self.init_device_group(hdf5_file)
        # write table to h5file if non-empty
        if len(acquisition_table):
            grp.create_dataset('ACQUISITIONS',compression=config.compression,
                                data=acquisition_table)
            grp['ACQUISITIONS'].attrs['trigger_time'] = self.trigger_time
                                
    def acquire(self,start_time):
        '''Call to define time when trigger will happen for scope.'''
        if not self.child_devices:
            raise LabscriptError('No channels acquiring for trigger {0:s}'.format(self.name))
        else:
            self.parent_device.trigger(start_time,self.trigger_duration)
            self.trigger_time = start_time

