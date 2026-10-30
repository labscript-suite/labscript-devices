#####################################################################
#                                                                   #
# /labscript_devices/CiceroOpalKellyXEM3001/blacs_tabs.py           #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################
from blacs.tab_base_classes import define_state, Tab
from blacs.tab_base_classes import (
    MODE_MANUAL,
    MODE_TRANSITION_TO_BUFFERED,
    MODE_TRANSITION_TO_MANUAL,
    MODE_BUFFERED,
)
from blacs.device_base_class import DeviceTab
from qtutils.qt.QtCore import *
from qtutils.qt.QtGui import *
from qtutils.qt.QtWidgets import *


class CiceroOpalKellyXEM3001Tab(DeviceTab):
    
    def initialise_GUI(self):
        # A variable to store whether the flash has filed. This will
        # inform the get_save_data() method as to whether to report the 
        # current reference clock configuration of the FPGA firmware
        self.failed_to_flash = False
    
        # Store the board number to be used
        connection_object = self.settings['connection_table'].find_by_name(self.device_name)
        self.serial = str(connection_object.BLACS_connection)
        self.reference_clock = connection_object.properties.get('reference_clock', 'internal')
        self.logger.debug('reference clock scheme is: %s', self.reference_clock)
        # Create and set the primary worker
        self.create_worker("main_worker", "labscript_devices.CiceroOpalKellyXEM3001.blacs_workers.CiceroOpalKellyXEM3001Worker", {'serial':self.serial, "reference_clock":self.reference_clock})
        self.primary_worker = "main_worker"
        
        # Set the capabilities of this device
        self.supports_smart_programming(False) 
        
        # Add button to force reflash
        self.flash_fpga_button = QToolButton()
        self.flash_fpga_button.setText('Flash FPGA firmware')
        self.flash_fpga_button.setToolTip('BLACS flashes the firmware automatically. Use this button if the device is not working correctly.')
        self.flash_fpga_button.setAutoRaise(True)
        self.flash_fpga_button.clicked.connect(self.flash_fpga)
        self.get_tab_layout().insertWidget(self.get_tab_layout().count()-1, self.flash_fpga_button)
        
     
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
            
        # If nothing found, Use default implementation
        return DeviceTab.get_child_from_connection_table(self, parent_device_name, port)
    
    def close_tab(self, *args, **kwargs):
        # disconnect method from button. This will allow the button to be garbage collected when it is shortly deleted
        self.flash_fpga_button.clicked.disconnect(self.flash_fpga)
        return Tab.close_tab(self, *args, **kwargs)
    
    def restore_save_data(self, data):
        # Flash the FPGA if the type of reference clock has changed since last time!
        if 'reference_clock' not in data or self.reference_clock != data['reference_clock']:
            self.flash_fpga()
    
    @define_state(MODE_MANUAL|MODE_BUFFERED|MODE_TRANSITION_TO_BUFFERED|MODE_TRANSITION_TO_MANUAL,True)
    def flash_fpga(self, ignore=None):
        ret = yield(self.queue_work(self.primary_worker, 'flash_FPGA'))
        if not ret:
            self.failed_to_flash = True
    
    def get_save_data(self):
        ret_data = {}
        # ignore the current reference clock configuration if we failed
        # to flash this time.
        # Note this will force a reflash next time the device is initialised
        if not self.failed_to_flash:
            ret_data['reference_clock'] = self.reference_clock
        return ret_data
     
    @define_state(MODE_BUFFERED|MODE_MANUAL,True)  
    def status_monitor(self, notify_queue):
        # remove the timeout if we are in manual mode (which happens when 
        # the abort button is clicked in BLACS)
        if self.mode == MODE_MANUAL:
            self.statemachine_timeout_remove(self.status_monitor)
            return
    
        status = yield(self.queue_work(self.primary_worker, 'status_monitor'))        
        if status:
            # Experiment is over. Tell the queue manager about it
            notify_queue.put('done')
            self.statemachine_timeout_remove(self.status_monitor)

        # handle exception in worker
        elif status is None:
            self.statemachine_timeout_remove(self.status_monitor)

            # TODO: This is a bit of a hack.
            # We fake a restart in order to notify the queue that something went wrong
            # and that it should abort the shot
            for f in self._restart_receiver:
                try:
                    f(self.device_name)
                except:
                    self.logger.exception('Could not notify a connected receiver function')
        
    @define_state(MODE_BUFFERED,True)  
    def start_run(self, notify_queue):
        """Starts the CiceroOpalKellyXEM3001, notifying the queue manager when
        the run is over"""
        # TODO: This 100ms (+ overhead) limits the minimum time you can have between 2 consecutive wait commands in labscript. Anything faster than this will not be detected properly.
        self.statemachine_timeout_add(100, self.status_monitor, notify_queue)
        yield(self.queue_work(self.primary_worker, 'start_run'))
