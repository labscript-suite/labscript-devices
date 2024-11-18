#####################################################################
#                                                                   #
# /naqslab_devices/KeysightDCSupply/blacs_tab.py                    #
#                                                                   #
# Copyright 2020, David Meyer                                       #
#                                                                   #
# This file is part of the naqslab devices extension to the         #
# labscript_suite. It is licensed under the Simplified BSD License. #
#                                                                   #
#                                                                   #
#####################################################################
from naqslab_devices.VISA.blacs_tab import VISATab 

# note, when adding a new model, put the labscript_device inheritor class
# into Models.py and the BLACS classes into a file named for the device
# in the BLACS subfolder. Update register_classes.py and __init__.py
# accordingly.
 
class KeysightDCSupplyTab(VISATab):

    status_byte_labels = {'bit 7':'Unregulated',
                          'bit 6':'Over-Voltage',
                          'bit 5':'Command Error',
                          'bit 4':'Execution Error',
                          'bit 3':'Device Error',
                          'bit 2':'Query Error',
                          'bit 1':'Constant Voltage Mode',
                          'bit 0':'Constant Current Mode'}
                          
    
    def __init__(self,*args,**kwargs):
        self.device_worker_class = 'naqslab_devices.KeysightDCSupply.blacs_worker.KeysightDCSupplyWorker'
        VISATab.__init__(self,*args,**kwargs)
    
    def initialise_GUI(self):
        # configure outputs based on output limiting type
        properties = self.settings['connection_table'].find_by_name(self.device_name).properties

        if properties['limited'] == 'volt':
            base_units = 'V'
            base_min = properties['volt_limits'][0]
            base_max = properties['volt_limits'][1]
        else:
            base_units = 'A'
            base_min = properties['current_limits'][0]
            base_max = properties['current_limits'][1]                                
        
        AO_prop = {} 
        for i in properties['allowed_outputs']:
            AO_prop['channel %d'%i] = {
                    'base_unit':base_units,
                    'min':base_min,
                    'max':base_max,
                    'step':1,
                    'decimals':5
            }
       
        # Create the output objects    
        self.create_analog_outputs(AO_prop)        
        # Create widgets for output objects
        dds_widgets,ao_widgets,do_widgets = self.auto_create_widgets()
        # and auto place the widgets in the UI
        self.auto_place_widgets(("DC Outputs",ao_widgets))
        
        # call VISATab.initialise to create STB widget
        VISATab.initialise_GUI(self)

        # Set the capabilities of this device
        self.supports_remote_value_check(True)
        self.supports_smart_programming(True) 
        self.statemachine_timeout_add(10000, self.status_monitor)       
