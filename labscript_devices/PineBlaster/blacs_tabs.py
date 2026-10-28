#####################################################################
#                                                                   #
# /labscript_devices/PineBlaster/blacs_tabs.py                      #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################
from blacs.tab_base_classes import define_state
from blacs.tab_base_classes import MODE_BUFFERED
from blacs.device_base_class import DeviceTab


class PineblasterTab(DeviceTab):
    
    def initialise_GUI(self):
        # Create a single digital output     
        self.create_digital_outputs({'internal':{}})        
        # Create widgets for output objects
        _,_,do_widgets = self.auto_create_widgets()
        # and auto place the widgets in the UI
        self.auto_place_widgets(("Flags", do_widgets))
        
        # Store the board number to be used
        self.usb_port = str(self.settings['connection_table'].find_by_name(self.device_name).BLACS_connection)
        # Create and set the primary worker
        self.create_worker("main_worker", "labscript_devices.PineBlaster.blacs_workers.PineblasterWorker", {'usbport':self.usb_port})
        self.primary_worker = "main_worker"
        
        # Set the capabilities of this device
        self.supports_smart_programming(True) 
     
    def get_child_from_connection_table(self, parent_device_name, port):
        # This is a direct output, let's search for it on the internal Pseudoclock
        if parent_device_name == self.device_name:
            device = self.connection_table.find_by_name(self.device_name)
            pseudoclock = device.child_list[list(device.child_list.keys())[0]] # there should always be one (and only one) child, the Pseudoclock
            clockline = None
            for child_name, child in pseudoclock.child_list.items():
                # store a reference to the internal clockline
                if child.parent_port == port:                
                    return DeviceTab.get_child_from_connection_table(self, pseudoclock.name, port)
            
        return '-'
        
     
    @define_state(MODE_BUFFERED,True)  
    def status_monitor(self, notify_queue):
        status = yield(self.queue_work(self.primary_worker, 'status_monitor'))        
        if status:
            # Experiment is over. Tell the queue manager about it
            notify_queue.put('done')
            self.statemachine_timeout_remove(self.status_monitor)
        
    @define_state(MODE_BUFFERED,True)  
    def start_run(self, notify_queue):
        """Starts the Pineblaster, notifying the queue manager when
        the run is over"""
        self.statemachine_timeout_add(100, self.status_monitor, notify_queue)
        yield(self.queue_work(self.primary_worker, 'start_run'))
