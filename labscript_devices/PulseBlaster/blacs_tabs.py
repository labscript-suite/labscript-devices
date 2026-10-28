#####################################################################
#                                                                   #
# /labscript_devices/PulseBlaster/blacs_tabs.py                     #
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
from blacs.tab_base_classes import (
    MODE_MANUAL,
    MODE_TRANSITION_TO_BUFFERED,
    MODE_TRANSITION_TO_MANUAL,
    MODE_BUFFERED,
)
from blacs.device_base_class import DeviceTab
from qtutils import UiLoader
from qtutils.icons import Icon
import os
from qtutils.qt import QtGui


    

class PulseBlasterTab(DeviceTab):
    
    def initialise_GUI(self):
        # Capabilities
        self.base_units     = {'freq':'Hz',        'amp':'Vpp', 'phase':'Degrees'}
        self.base_min       = {'freq':0.3,         'amp':0.0,   'phase':0}
        self.base_max       = {'freq':150000000.0, 'amp':1.0,   'phase':360}
        self.base_step      = {'freq':1000000,     'amp':0.01,  'phase':1}
        self.base_decimals  = {'freq':1,           'amp':3,     'phase':3}
        self.num_DDS = 2
        self.num_DO = 12
        
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
        
        do_prop = {}
        for i in range(self.num_DO): # 12 is the maximum number of flags on this device (some only have 4 though)
            do_prop['flag %d'%i] = {}
        
        # Create the output objects    
        self.create_dds_outputs(dds_prop)        
        self.create_digital_outputs(do_prop)        
        # Create widgets for output objects
        dds_widgets,ao_widgets,do_widgets = self.auto_create_widgets()
        
        # Define the sort function for the digital outputs
        def sort(channel):
            flag = channel.replace('flag ','')
            flag = int(flag)
            return '%02d'%(flag)
        
        # and auto place the widgets in the UI
        self.auto_place_widgets(("DDS Outputs",dds_widgets),("Flags",do_widgets,sort))
        
        # Store the board number to be used
        connection_object = self.settings['connection_table'].find_by_name(self.device_name)
        self.board_number = int(connection_object.BLACS_connection)
        
        # And which scheme we're using for buffered output programming and triggering:
        # (default values for backward compat with old connection tables)
        self.programming_scheme = connection_object.properties.get('programming_scheme', 'pb_start/BRANCH')
            
        # Create and set the primary worker
        self.create_worker("main_worker","labscript_devices.PulseBlaster.blacs_workers.PulseblasterWorker",{'board_number':self.board_number,
                                                             'programming_scheme': self.programming_scheme})
        self.primary_worker = "main_worker"
        
        # Set the capabilities of this device
        self.supports_smart_programming(True) 
        
        # Load status monitor (and start/stop/reset buttons) UI
        ui = UiLoader().load(os.path.join(os.path.dirname(os.path.realpath(__file__)),'pulseblaster.ui'))        
        self.get_tab_layout().addWidget(ui)
        # Connect signals for buttons
        ui.start_button.clicked.connect(self.start)
        ui.stop_button.clicked.connect(self.stop)
        ui.reset_button.clicked.connect(self.reset)
        # Add icons
        ui.start_button.setIcon(QtGui.QIcon(':/qtutils/fugue/control'))
        ui.start_button.setToolTip('Start')
        ui.stop_button.setIcon(QtGui.QIcon(':/qtutils/fugue/control-stop-square'))
        ui.stop_button.setToolTip('Stop')
        ui.reset_button.setIcon(QtGui.QIcon(':/qtutils/fugue/arrow-circle'))
        ui.reset_button.setToolTip('Reset')
        
        # initialise dictionaries of data to display and get references to the QLabels
        self.status_states = ['stopped', 'reset', 'running', 'waiting']
        self.status = {}
        self.status_widgets = {}
        for state in self.status_states:
            self.status[state] = False
            self.status_widgets[state] = getattr(ui,'%s_label'%state)        
        
        # Create status monitor timout
        self.statemachine_timeout_add(2000, self.status_monitor)
        
    def get_child_from_connection_table(self, parent_device_name, port):
        # This is a direct output, let's search for it on the internal intermediate device called 
        # PulseBlasterDirectOutputs
        if parent_device_name == self.device_name:
            device = self.connection_table.find_by_name(self.device_name)
            pseudoclock = device.child_list[list(device.child_list.keys())[0]] # there should always be one (and only one) child, the Pseudoclock
            clockline = None
            for child_name, child in pseudoclock.child_list.items():
                # store a reference to the internal clockline
                if child.parent_port == 'internal':
                    clockline = child
                # if the port is in use by a clockline, return the clockline
                elif child.parent_port == port:
                    return child
                
            if clockline is not None:
                # There should only be one child of this clock line, the direct outputs
                direct_outputs = clockline.child_list[list(clockline.child_list.keys())[0]]
                # look to see if the port is used by a child of the direct outputs
                return DeviceTab.get_child_from_connection_table(self, direct_outputs.name, port)
            else:
                return ''
        else:
            # else it's a child of a DDS, so we can use the default behaviour to find the device
            return DeviceTab.get_child_from_connection_table(self, parent_device_name, port)
    
    # This function gets the status of the Pulseblaster from the spinapi,
    # and updates the front panel widgets!
    @define_state(MODE_MANUAL|MODE_BUFFERED|MODE_TRANSITION_TO_BUFFERED|MODE_TRANSITION_TO_MANUAL,True)  
    def status_monitor(self,notify_queue=None):
        # When called with a queue, this function writes to the queue
        # when the pulseblaster is waiting. This indicates the end of
        # an experimental run.
        self.status, waits_pending, time_based_shot_over = yield(self.queue_work(self._primary_worker,'check_status'))
        
        if self.programming_scheme == 'pb_start/BRANCH':
            done_condition = self.status['waiting']
        elif self.programming_scheme == 'pb_stop_programming/STOP':
            done_condition = self.status['stopped']
            
        if time_based_shot_over is not None:
            done_condition = time_based_shot_over
            
        if notify_queue is not None and done_condition and not waits_pending:
            # Experiment is over. Tell the queue manager about it, then
            # set the status checking timeout back to every 2 seconds
            # with no queue.
            notify_queue.put('done')
            self.statemachine_timeout_remove(self.status_monitor)
            self.statemachine_timeout_add(2000,self.status_monitor)
            if self.programming_scheme == 'pb_stop_programming/STOP':
                # Not clear that on all models the outputs will be correct after being
                # stopped this way, so we do program_manual with current values to be sure:
                self.program_device()
                
        # Update widgets with new status
        for state in self.status_states:
            if self.status[state]:
                icon = Icon(':/qtutils/fugue/tick')
            else:
                icon = Icon(':/qtutils/fugue/cross')
            self.status_widgets[state].setIcon(icon)
                        
    @define_state(MODE_MANUAL|MODE_BUFFERED|MODE_TRANSITION_TO_BUFFERED|MODE_TRANSITION_TO_MANUAL,True)  
    def start(self,widget=None):
        yield(self.queue_work(self._primary_worker,'start_run'))
        self.status_monitor()
        
    @define_state(MODE_MANUAL|MODE_BUFFERED|MODE_TRANSITION_TO_BUFFERED|MODE_TRANSITION_TO_MANUAL,True)  
    def stop(self,widget=None):
        yield(self.queue_work(self._primary_worker,'pb_stop'))
        self.status_monitor()
        
    @define_state(MODE_MANUAL|MODE_BUFFERED|MODE_TRANSITION_TO_BUFFERED|MODE_TRANSITION_TO_MANUAL,True)  
    def reset(self,widget=None):
        yield(self.queue_work(self._primary_worker,'pb_reset'))
        self.status_monitor()
    
    @define_state(MODE_BUFFERED,True)  
    def start_run(self, notify_queue):
        """Starts the Pulseblaster, notifying the queue manager when
        the run is over"""
        self.statemachine_timeout_remove(self.status_monitor)
        self.start()
        self.statemachine_timeout_add(100,self.status_monitor,notify_queue)
