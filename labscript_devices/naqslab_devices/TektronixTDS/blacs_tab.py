#####################################################################
#                                                                   #
# /naqslab_devices/TektronixTDS/blacs_tab.py                        #
#                                                                   #
# Copyright 2018, David Meyer                                       #
#                                                                   #
# This file is part of the naqslab devices extension to the         #
# labscript_suite. It is licensed under the Simplified BSD License. #
#                                                                   #
#                                                                   #
#####################################################################
from naqslab_devices.VISA.blacs_tab import VISATab 


class TDS_ScopeTab(VISATab):
    # Event Byte Label Definitions for TDS200/1000/2000 series scopes
    # Used bits set by '*ESE' command in setup string of worker class
    status_byte_labels = {'bit 7':'Unused', 
                          'bit 6':'Unused',
                          'bit 5':'Command Error',
                          'bit 4':'Execution Error',
                          'bit 3':'Device Error',
                          'bit 2':'Query Error',
                          'bit 1':'Unused',
                          'bit 0':'Unused'}
    
    def __init__(self,*args,**kwargs):
        if not hasattr(self,'device_worker_class'):
            self.device_worker_class = 'naqslab_devices.TektronixTDS.blacs_worker.TDS_ScopeWorker'
        VISATab.__init__(self,*args,**kwargs)
    
    def initialise_GUI(self):
        # Call the VISATab parent to initialise the STB ui and set the worker
        VISATab.initialise_GUI(self)

        # Set the capabilities of this device
        self.supports_remote_value_check(False)
        self.supports_smart_programming(False) 
        self.statemachine_timeout_add(5000, self.status_monitor)        
       
