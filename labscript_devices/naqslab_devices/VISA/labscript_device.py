#####################################################################
#                                                                   #
# /naqslab_devices/VISA/labscript_device.py                         #
#                                                                   #
# Copyright 2018, David Meyer                                       #
#                                                                   #
# This file is part of the naqslab devices extension to the         #
# labscript_suite. It is licensed under the Simplified BSD License. #
#                                                                   #
#                                                                   #
#####################################################################
"""
Boiler plate labscript_device for VISA instruments. 
"""
from labscript import Device, LabscriptError, set_passed_properties

__version__ = '0.1.1'
__author__ = ['dihm']
                  
class VISA(Device):
    description = 'VISA Compatible Instrument'
    allowed_children = []
    
    @set_passed_properties(property_names = {
        "device_properties":["VISA_name"]}
        )
    def __init__(self, name, parent_device, VISA_name, **kwargs):
        """Base VISA labscript_device class.
        
        Inheritors should call VISA.__init__() in their own __init__() method.
        Generate_code must be overridden.
        
        Args:
            name (str): name of device in connectiontable
            parent_device (obj): Handle to any parent device.
            VISA_name (str): Can be full VISA connection string or NI-MAX alias.
        """
        self.VISA_name = VISA_name
        self.BLACS_connection = VISA_name
        Device.__init__(self, name, parent_device, VISA_name)
        
    def generate_code(self, hdf5_file):
        """Method to generate instructions for blacs_worker to program device.
        
        Must be over-ridden."""
        raise LabscriptError('generate_code() must be overridden for {0:s}'.format(self.name))

