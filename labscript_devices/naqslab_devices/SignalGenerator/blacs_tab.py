#####################################################################
#                                                                   #
# /naqslab_devices/SignalGenerator/blacs_tab.py                     #
#                                                                   #
# Copyright 2018, David Meyer                                       #
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


class SignalGeneratorTab(VISATab):
    # Capabilities
    base_units = {'freq':'MHz', 'amp':'dBm'}
    base_min = {'freq':0.1,   'amp':-140}
    base_max = {'freq':1057.5,  'amp':20}
    base_step = {'freq':1,    'amp':0.1}
    base_decimals = {'freq':6, 'amp':1}

    status_byte_labels = {'bit 7':'bit 7 label', 
                          'bit 6':'bit 6 label',
                          'bit 5':'bit 5 label',
                          'bit 4':'bit 4 label',
                          'bit 3':'bit 3 label',
                          'bit 2':'bit 2 label',
                          'bit 1':'bit 1 label',
                          'bit 0':'bit 0 label'}
    
    def __init__(self,*args,**kwargs):
        if not hasattr(self,'device_worker_class'):
            #raise LabscriptError('%s __init__ method not overridden!'%self)
            self.device_worker_class = 'naqslab_devices.SignalGenerator.blacs_worker.SignalGeneratorWorker'
        VISATab.__init__(self,*args,**kwargs)

    def initialise_GUI(self):
        # Create the dds channel
        dds_prop = {}
        dds_prop['channel 0'] = {} #HP signal generators only have one output
        for subchnl in ['freq', 'amp']:
            dds_prop['channel 0'][subchnl] = {'base_unit':self.base_units[subchnl],
                                              'min':self.base_min[subchnl],
                                              'max':self.base_max[subchnl],
                                              'step':self.base_step[subchnl],
                                              'decimals':self.base_decimals[subchnl]
                                              }
        dds_prop['channel 0']['gate'] = {}


        # Create the output objects
        self.create_dds_outputs(dds_prop)
        # Create widgets for output objects
        dds_widgets,ao_widgets,do_widgets = self.auto_create_widgets()
        # and auto place the widgets in the UI
        self.auto_place_widgets(("Frequency Output",dds_widgets))
        
        # call VISATab.initialise to create STB widget
        VISATab.initialise_GUI(self)

        # Set the capabilities of this device
        self.supports_remote_value_check(True)
        self.supports_smart_programming(True) 
        self.statemachine_timeout_add(10000, self.status_monitor)       
