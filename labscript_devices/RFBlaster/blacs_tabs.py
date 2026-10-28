#####################################################################
#                                                                   #
# RFblaster.py                                                      #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from blacs.tab_base_classes import define_state
from blacs.tab_base_classes import MODE_MANUAL, MODE_TRANSITION_TO_MANUAL, MODE_BUFFERED
from blacs.device_base_class import DeviceTab


class RFBlasterTab(DeviceTab):
    def initialise_GUI(self):
        # Capabilities 
        self.base_units =     {'freq':'Hz',        'amp':'%',         'phase':'Degrees'}
        self.base_min =       {'freq':500000,      'amp':0.0,         'phase':0}
        self.base_max =       {'freq':350000000.0, 'amp':99.99389648, 'phase':360}
        self.base_step =      {'freq':1000000,     'amp':1.0,         'phase':1}
        #TODO: Find out what the amp and phase precision is
        self.base_decimals =  {'freq':1,           'amp':3,           'phase':3}
        self.num_DDS = 2  

        # Create DDS Output objects
        dds_prop = {}
        for i in range(self.num_DDS): # 2 is the number of DDS outputs on this device
            dds_prop['dds %d'%i] = {}
            for subchnl in ['freq', 'amp', 'phase']:
                dds_prop['dds %d'%i][subchnl] = {'base_unit':self.base_units[subchnl],
                                                 'min':self.base_min[subchnl],
                                                 'max':self.base_max[subchnl],
                                                 'step':self.base_step[subchnl],
                                                 'decimals':self.base_decimals[subchnl]
                                                }
            dds_prop['dds %d'%i]['gate'] = {}
                
        # Create the output objects    
        self.create_dds_outputs(dds_prop)        
        # Create widgets for output objects
        dds_widgets,ao_widgets,do_widgets = self.auto_create_widgets()
        # and auto place the widgets in the UI
        self.auto_place_widgets(("DDS Outputs",dds_widgets))
        
        # Store the COM port to be used
        self.address = "http://" + str(self.BLACS_connection) + ":8080"
        
        # Create and set the primary worker
        self.create_worker("main_worker", "labscript_devices.RFBlaster.blacs_workers.RFBlasterWorker", {'address': self.address, 'num_DDS': self.num_DDS})
        self.primary_worker = "main_worker"

        # Set the capabilities of this device
        self.supports_remote_value_check(True)
        self.supports_smart_programming(False) 
    
    def get_child_from_connection_table(self, parent_device_name, port):
        # This is a direct output, let's search for it on the internal intermediate device called 
        # RFBlasterDirectOutputs
        if parent_device_name == self.device_name:
            device = self.connection_table.find_by_name(self.device_name)
            pseudoclock = device.child_list[list(device.child_list.keys())[0]] # there should always be one (and only one) child, the Pseudoclock
            clockline = pseudoclock.child_list[list(pseudoclock.child_list.keys())[0]] # there should always be one (and only one) child, the clockline
            direct_outputs = clockline.child_list[list(clockline.child_list.keys())[0]] # There should only be one child of this clock line, the direct outputs
            # look to see if the port is used by a child of the direct outputs
            return DeviceTab.get_child_from_connection_table(self, direct_outputs.name, port)
        else:
            # else it's a child of a DDS, so we can use the default behaviour to find the device
            return DeviceTab.get_child_from_connection_table(self, parent_device_name, port)
    
    # We override this because the RFBlaster doesn't really support remote_value_checking properly
    # Here we specifically do not program the device (it's slow!) nor do we update the last programmed value to the current
    # front panel state. This is because the remote value returned from the RFBlaster is always the last *manual* values programmed.
    @define_state(MODE_BUFFERED,False)
    def transition_to_manual(self,notify_queue,program=False):
        self.mode = MODE_TRANSITION_TO_MANUAL
        
        success = yield(self.queue_work(self._primary_worker,'transition_to_manual'))
        for worker in self._secondary_workers:
            transition_success = yield(self.queue_work(worker,'transition_to_manual'))
            if not transition_success:
                success = False
                # don't break here, so that as much of the device is returned to normal
        
        # Update the GUI with the final values of the run:
        for channel, value in self._final_values.items():
            if channel in self._AO:
                self._AO[channel].set_value(value,program=False)
            elif channel in self._DO:
                self._DO[channel].set_value(value,program=False)
            elif channel in self._DDS:
                self._DDS[channel].set_value(value,program=False)
        
        if success:
            notify_queue.put([self.device_name,'success'])
            self.mode = MODE_MANUAL
        else:
            notify_queue.put([self.device_name,'fail'])
            raise Exception('Could not transition to manual. You must restart this device to continue')
