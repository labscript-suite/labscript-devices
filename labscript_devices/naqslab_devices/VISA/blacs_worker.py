#####################################################################
#                                                                   #
# /naqslab_devices/VISA/blacs_worker.py                             #
#                                                                   #
# Copyright 2018, David Meyer                                       #
#                                                                   #
# This file is part of the naqslab devices extension to the         #
# labscript_suite. It is licensed under the Simplified BSD License. #
#                                                                   #
#                                                                   #
#####################################################################
"""
Boiler plate BLACS_worker for VISA instruments.

Inheritors use the same communication protocol, but override the command syntax.
"""
from blacs.tab_base_classes import Worker

from labscript import LabscriptError
from labscript_utils import dedent

import pyvisa as visa

class VISAWorker(Worker):   
    def init(self):
        """Initializes basic worker and opens VISA connection to device.
        
        Default connection timeout is 2 seconds"""    
        self.VISA_name = self.address
        self.resourceMan = visa.ResourceManager()
        try:
            self.connection = self.resourceMan.open_resource(self.VISA_name)
        except visa.VisaIOError:
            msg = '''{:s} not found! Is it connected?'''.format(self.VISA_name)
            raise LabscriptError(dedent(msg)) from None
        self.connection.timeout = 2000
    
    def check_remote_values(self):
        # over-ride this method if remote value check is supported
        return None
    
    def convert_register(self,register):
        """Converts returned register value to dict of bools
        
        Args:
            register (int): Status register value returned from 
                            :obj:`read_stb <pyvisa.highlevel.VisaLibraryBase.read_stb>`
            
        Returns:
            dict: Status byte dictionary as formatted in :obj:`VISATab`
        """
        results = {}
        #get the status and convert to binary, and take off the '0b' header:
        status = bin(register)[2:]
        # if the status is less than 8 bits long, pad the start with zeros!
        while len(status)<8:
            status = '0'+status
        # reverse the status string so bit 0 is first indexed
        status = status[::-1]
        # fill the status byte dictionary
        for i in range(0,8):
            results['bit '+str(i)] = bool(int(status[i]))
        
        return results
    
    def check_status(self):
        """Reads the Status Byte Register of the VISA device.
        
        Returns:
            dict: Status byte dictionary as formatted in :obj:`VISATab`
        """
        results = {}
        stb = self.connection.read_stb()
        
        return self.convert_register(stb)
    
    def program_manual(self,front_panel_values):
        """Over-ride this method if remote programming is supported.
        
        Returns:
            :obj:`VISAWorker.check_remote_values()`
        """

        return self.check_remote_values()
        
    def clear(self,value):
        """Sends standard \*CLR to clear registers of device.
        
        Args:
            value (bool): value of Clear button in STBstatus.ui widget
        """
        self.connection.clear()
        
    def transition_to_buffered(self,device_name,h5file,initial_values,fresh):
        """Stores various device handles for use in transition_to_manual method.
        
        Automatically called by BLACS. Should be over-ridden by inheritors.
        
        Args:
            device_name (str): Name of device from connectiontable
            h5file (str): path to shot h5_file
            initial_values (dict): Contains the start of shot values
            fresh (bool): Indicates if smart_programming should be refreshed this shot
        """
        # Store the initial values in case we have to abort and restore them:
        self.initial_values = initial_values
        # Store the final values to for use during transition_to_static:
        self.final_values = {}
        # Store some parameters for saving data later
        self.h5_file = h5file
        self.device_name = device_name
                
        return self.final_values
        
    def abort_transition_to_buffered(self):
        """Special abort shot configuration code belongs here.
        """
        return self.transition_to_manual(True)
        
    def abort_buffered(self):
        """Special abort shot code belongs here.
        """
        return self.transition_to_manual(True)
            
    def transition_to_manual(self,abort = False):
        """Simple transition_to_manual method where no data is saved."""         
        if abort:
            # If we're aborting the run, reset to original value
            self.program_manual(self.initial_values)
        # If we're not aborting the run, stick with buffered value. Nothing to do really!
        # return the current values in the device
        return True
        
    def shutdown(self):
        """Closes VISA connection to device."""
        self.connection.close()

