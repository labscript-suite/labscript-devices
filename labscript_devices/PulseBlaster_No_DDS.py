#####################################################################
#                                                                   #
# /Pulseblaster_No_DDS.py                                           #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

from labscript_devices import BLACS_tab, runviewer_parser
from labscript_devices.PulseBlaster import PulseBlaster, PulseBlasterParser
from labscript import PseudoclockDevice, config

import numpy as np


class PulseBlaster_No_DDS(PulseBlaster):

    description = 'generic DO only Pulseblaster'
    clock_limit = 8.3e6 # can probably go faster
    clock_resolution = 20e-9
    n_flags = 24
    core_clock_freq = 100 # MHz
    
    def write_pb_inst_to_h5(self, pb_inst, hdf5_file):
        # OK now we squeeze the instructions into a numpy array ready for writing to hdf5:
        pb_dtype= [('flags',np.int32), ('inst',np.int32), ('inst_data',np.int32), ('length',np.float64)]
        pb_inst_table = np.empty(len(pb_inst),dtype = pb_dtype)
        for i,inst in enumerate(pb_inst):
            flagint = int(inst['flags'][::-1],2)
            instructionint = self.pb_instructions[inst['instruction']]
            dataint = inst['data']
            delaydouble = inst['delay']
            pb_inst_table[i] = (flagint, instructionint, dataint, delaydouble)
        
        # Okay now write it to the file: 
        group = hdf5_file['/devices/'+self.name]  
        group.create_dataset('PULSE_PROGRAM', compression=config.compression,data = pb_inst_table)         
        self.set_property('stop_time', self.stop_time, location='device_properties')
        
    def generate_code(self, hdf5_file):
        # Generate the hardware instructions
        self.init_device_group(hdf5_file)
        PseudoclockDevice.generate_code(self, hdf5_file)
        dig_outputs, ignore = self.get_direct_outputs()
        pb_inst = self.convert_to_pb_inst(dig_outputs, [], {}, {}, {})
        self._check_wait_monitor_ok()
        self.write_pb_inst_to_h5(pb_inst, hdf5_file) 
        

from blacs.tab_base_classes import Worker, define_state
from blacs.tab_base_classes import MODE_MANUAL, MODE_TRANSITION_TO_BUFFERED, MODE_TRANSITION_TO_MANUAL, MODE_BUFFERED  

from blacs.device_base_class import DeviceTab

from qtutils import UiLoader
import qtutils.icons
import os

# We can't import * from QtCore & QtGui, as one of them has a function called bin() which overrides the builtin, which is used in the pulseblaster worker
from qtutils.qt import QtCore
from qtutils.qt import QtGui
from qtutils.qt import QtWidgets

@BLACS_tab
class Pulseblaster_No_DDS_Tab(DeviceTab):
    # Capabilities
    num_DO = 24
    def __init__(self,*args,**kwargs):
        if not hasattr(self,'device_worker_class'):
            self.device_worker_class = PulseblasterNoDDSWorker
        DeviceTab.__init__(self,*args,**kwargs)
        
    def initialise_GUI(self):
        do_prop = {}
        for i in range(self.num_DO): # 12 is the maximum number of flags on this device (some only have 4 though)
            do_prop['flag %d'%i] = {}
        
        # Create the output objects         
        self.create_digital_outputs(do_prop)        
        # Create widgets for output objects
        dds_widgets,ao_widgets,do_widgets = self.auto_create_widgets()
        
        # Define the sort function for the digital outputs
        def sort(channel):
            flag = channel.replace('flag ','')
            flag = int(flag)
            return '%02d'%(flag)
        
        # and auto place the widgets in the UI
        self.auto_place_widgets(("Flags",do_widgets,sort))
        
        # Store the board number to be used
        connection_object = self.settings['connection_table'].find_by_name(self.device_name)
        self.board_number = int(connection_object.BLACS_connection)
        
        # And which scheme we're using for buffered output programming and triggering:
        # (default values for backward compat with old connection tables)
        self.programming_scheme = connection_object.properties.get('programming_scheme', 'pb_start/BRANCH')
        
        # Create and set the primary worker
        self.create_worker("main_worker",self.device_worker_class,{'board_number':self.board_number,
                                                                   'num_DO': self.num_DO,
                                                                   'programming_scheme': self.programming_scheme})
        self.primary_worker = "main_worker"
        
        # Set the capabilities of this device
        self.supports_smart_programming(True) 
        
        #### adding status widgets from PulseBlaster.py
        
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
        
        # Status monitor timout
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
                icon = QtGui.QIcon(':/qtutils/fugue/tick')
            else:
                icon = QtGui.QIcon(':/qtutils/fugue/cross')
            
            pixmap = icon.pixmap(QtCore.QSize(16, 16))
            self.status_widgets[state].setPixmap(pixmap)
        
    
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


class PulseblasterNoDDSWorker(Worker):
    core_clock_freq = 100
    def init(self):
        exec('from spinapi import *', globals())
        global h5py; import labscript_utils.h5_lock, h5py
        global zprocess; import zprocess
        
        self.pb_start = pb_start
        self.pb_stop = pb_stop
        self.pb_reset = pb_reset
        self.pb_close = pb_close
        self.pb_read_status = pb_read_status
        self.smart_cache = {'pulse_program':None,'ready_to_go':False,
                            'initial_values':None}
                            
        # An event for checking when all waits (if any) have completed, so that
        # we can tell the difference between a wait and the end of an experiment.
        # The wait monitor device is expected to post such events, which we'll wait on:
        self.all_waits_finished = zprocess.Event('all_waits_finished')
        self.waits_pending = False
    
        pb_select_board(self.board_number)
        pb_init()
        pb_core_clock(self.core_clock_freq)
        
        # This is only set to True on a per-shot basis, so set it to False
        # for manual mode. Set associated attributes to None:
        self.time_based_stop_workaround = False
        self.time_based_shot_duration = None
        self.time_based_shot_end_time = None

    def program_manual(self,values):
        # Program the DDS registers:
        
        # create flags string
        # NOTE: The spinapi can take a string or integer for flags.
                # If it is a string: 
                #     flag: 0          12
                #          '101100011111'
                #
                # If it is a binary number:
                #     flag:12          0
                #         0b111110001101
                #
                # Be warned!
        flags = ''
        for i in range(self.num_DO):
            if values['flag %d'%i]:
                flags += '1'
            else:
                flags += '0'
        
        if self.programming_scheme == 'pb_stop_programming/STOP':
            # Need to ensure device is stopped before programming - or we won't know what line it's on.
            pb_stop()
            
        # Write the first two lines of the pulse program:
        pb_start_programming(PULSE_PROGRAM)
        # Line zero is a wait:
        pb_inst_pbonly(flags, WAIT, 0, 100)
        # Line one is a brach to line 0:
        pb_inst_pbonly(flags, BRANCH, 0, 100)
        pb_stop_programming()
        
        # Now we're waiting on line zero, so when we start() we'll go to
        # line one, then brach back to zero, completing the static update:
        pb_start()
        
        # The pulse program now has a branch in line one, and so can't proceed to the pulse program
        # without a reprogramming of the first two lines:
        self.smart_cache['ready_to_go'] = False
        
        # TODO: return coerced/quantised values
        return {}
        
    def start_run(self):
        if self.programming_scheme == 'pb_start/BRANCH':
            pb_start()
        elif self.programming_scheme == 'pb_stop_programming/STOP':
            pb_stop_programming()
            pb_start()
        else:
            raise ValueError('invalid programming_scheme: %s'%str(self.programming_scheme))
        if self.time_based_stop_workaround:
            import time
            self.time_based_shot_end_time = time.time() + self.time_based_shot_duration
            
    def transition_to_buffered(self,device_name,h5file,initial_values,fresh):
        self.h5file = h5file
        if self.programming_scheme == 'pb_stop_programming/STOP':
            # Need to ensure device is stopped before programming - or we wont know what line it's on.
            pb_stop()
        with h5py.File(h5file,'r') as hdf5_file:
            group = hdf5_file['devices/%s'%device_name]
                          
            # Is this shot using the fixed-duration workaround instead of checking the PulseBlaster's status?
            self.time_based_stop_workaround = group.attrs.get('time_based_stop_workaround', False)
            if self.time_based_stop_workaround:
                self.time_based_shot_duration = (group.attrs['stop_time']
                                                 + hdf5_file['waits'][:]['timeout'].sum()
                                                 + group.attrs['time_based_stop_workaround_extra_time'])
            
            # Now for the pulse program:
            pulse_program = group['PULSE_PROGRAM'][2:]
            
            #Let's get the final state of the pulseblaster. z's are the args we don't need:
            flags,z,z,z = pulse_program[-1]
            
            # Always call start_programming regardless of whether we are going to do any
            # programming or not. This is so that is the programming_scheme is 'pb_stop_programming/STOP'
            # we are ready to be triggered by a call to pb_stop_programming() even if no programming
            # occurred due to smart programming:
            pb_start_programming(PULSE_PROGRAM)
            
            if fresh or (self.smart_cache['initial_values'] != initial_values) or \
                (len(self.smart_cache['pulse_program']) != len(pulse_program)) or \
                (self.smart_cache['pulse_program'] != pulse_program).any() or \
                not self.smart_cache['ready_to_go']:
            
                self.smart_cache['ready_to_go'] = True
                self.smart_cache['initial_values'] = initial_values

                # create initial flags string
                # NOTE: The spinapi can take a string or integer for flags.
                # If it is a string: 
                #     flag: 0          12
                #          '101100011111'
                #
                # If it is a binary number:
                #     flag:12          0
                #         0b111110001101
                #
                # Be warned!
                initial_flags = ''
                for i in range(self.num_DO):
                    if initial_values['flag %d'%i]:
                        initial_flags += '1'
                    else:
                        initial_flags += '0'

                if self.programming_scheme == 'pb_start/BRANCH':
                    # Line zero is a wait on the final state of the program in 'pb_start/BRANCH' mode 
                    pb_inst_pbonly(flags,WAIT,0,100)
                else:
                    # Line zero otherwise just contains the initial flags 
                    pb_inst_pbonly(initial_flags,CONTINUE,0,100)
                                        
                # Line one is a continue with the current front panel values:
                pb_inst_pbonly(initial_flags, CONTINUE, 0, 100)
                # Now the rest of the program:
                if fresh or len(self.smart_cache['pulse_program']) != len(pulse_program) or \
                (self.smart_cache['pulse_program'] != pulse_program).any():
                    self.smart_cache['pulse_program'] = pulse_program
                    for args in pulse_program:
                        pb_inst_pbonly(*args)
                        
            if self.programming_scheme == 'pb_start/BRANCH':
                # We will be triggered by pb_start() if we are are the master pseudoclock or a single hardware trigger
                # from the master if we are not:
                pb_stop_programming()
            elif self.programming_scheme == 'pb_stop_programming/STOP':
                # Don't call pb_stop_programming(). We don't want to pulseblaster to respond to hardware
                # triggers (such as 50/60Hz line triggers) until we are ready to run.
                # Our start_method will call pb_stop_programming() when we are ready
                pass
            else:
                raise ValueError('invalid programming_scheme %s'%str(self.programming_scheme))
            
            # Are there waits in use in this experiment? The monitor waiting for the end
            # of the experiment will need to know:
            wait_monitor_exists = bool(hdf5_file['waits'].attrs['wait_monitor_acquisition_device'])
            waits_in_use = bool(len(hdf5_file['waits']))
            self.waits_pending = wait_monitor_exists and waits_in_use
            if waits_in_use and not wait_monitor_exists:
                # This should be caught during labscript compilation, but just in case.
                # having waits but not a wait monitor means we can't tell when the shot
                # is over unless the shot ends in a STOP instruction:
                assert self.programming_scheme == 'pb_stop_programming/STOP'
            
            # Now we build a dictionary of the final state to send back to the GUI:
            return_values = {}
            # Since we are converting from an integer to a binary string, we need to reverse the string! (see notes above when we create flags variables)
            return_flags = str(bin(flags)[2:]).rjust(self.num_DO,'0')[::-1]
            for i in range(self.num_DO):
                return_values['flag %d'%i] = return_flags[i]
                
            return return_values
            
    def check_status(self):
        if self.waits_pending:
            try:
                self.all_waits_finished.wait(self.h5file, timeout=0)
                self.waits_pending = False
            except zprocess.TimeoutError:
                pass
        if self.time_based_shot_end_time is not None:
            import time
            time_based_shot_over = time.time() > self.time_based_shot_end_time
        else:
            time_based_shot_over = None
        return pb_read_status(), self.waits_pending, time_based_shot_over
        
    def transition_to_manual(self):
        status, waits_pending, time_based_shot_over = self.check_status()
        
        if self.programming_scheme == 'pb_start/BRANCH':
            done_condition = status['waiting']
        elif self.programming_scheme == 'pb_stop_programming/STOP':
            done_condition = status['stopped']
            
        if time_based_shot_over is not None:
            done_condition = time_based_shot_over
        
        # This is only set to True on a per-shot basis, so reset it to False
        # for manual mode. Reset associated attributes to None:
        self.time_based_stop_workaround = False
        self.time_based_shot_duration = None
        self.time_based_shot_end_time = None
        
        if done_condition and not waits_pending:
            return True
        else:
            return False
     
    def abort_buffered(self):
        # Stop the execution
        self.pb_stop()
        # Reset to the beginning of the pulse sequence
        self.pb_reset()
                
        # abort_buffered in the GUI process queues up a program_device state
        # which will reprogram the device and call pb_start()
        # This ensures the device isn't accidentally retriggered by another device
        # while it is running it's abort function
        return True
        
    def abort_transition_to_buffered(self):
        return True
        
    def shutdown(self):
        #TODO: implement this
        pass
        
@runviewer_parser
class PulseBlaster_No_DDS_Parser(PulseBlasterParser):
    num_dds = 0
    num_flags = 24

