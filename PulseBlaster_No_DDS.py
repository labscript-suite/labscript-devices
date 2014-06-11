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

from labscript_devices import labscript_device, BLACS_tab, BLACS_worker, runviewer_parser
from labscript_devices.PulseBlaster import PulseBlaster

@labscript_device
class PulseBlaster_No_DDS(PulseBlaster):

    description = 'generic DO only Pulseblaster'
    clock_limit = 8.3e6 # can probably go faster
    clock_resolution = 20e-9
    n_flags = 24
    
    def write_pb_inst_to_h5(self, pb_inst, hdf5_file):
        # OK now we squeeze the instructions into a numpy array ready for writing to hdf5:
        pb_dtype = [('flags',int32), ('inst',int32),
                    ('inst_data',int32), ('length',float64)]
        pb_inst_table = empty(len(pb_inst),dtype = pb_dtype)
        for i,inst in enumerate(pb_inst):
            flagint = int(inst['flags'][::-1],2)
            instructionint = self.pb_instructions[inst['instruction']]
            dataint = inst['data']
            delaydouble = inst['delay']
            pb_inst_table[i] = (flagint, instructionint, dataint, delaydouble)
        
        # Okay now write it to the file: 
        group = hdf5_file['/devices/'+self.name]  
        group.create_dataset('PULSE_PROGRAM', compression=config.compression,data = pb_inst_table)         
        group.attrs['stop_time'] = self.stop_time     
        
    def generate_code(self, hdf5_file):
        # Generate the hardware instructions
        hdf5_file.create_group('/devices/'+self.name)
        PseudoClock.generate_code(self, hdf5_file)
        dig_outputs, ignore = self.get_direct_outputs()
        pb_inst = self.convert_to_pb_inst(dig_outputs, [], {}, {}, {})
        self.write_pb_inst_to_h5(pb_inst, hdf5_file) 
        

from blacs.tab_base_classes import Worker, define_state
from blacs.tab_base_classes import MODE_MANUAL, MODE_TRANSITION_TO_BUFFERED, MODE_TRANSITION_TO_MANUAL, MODE_BUFFERED  

from blacs.device_base_class import DeviceTab

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
        self.board_number = int(self.settings['connection_table'].find_by_name(self.device_name).BLACS_connection)
        
        # Create and set the primary worker
        self.create_worker("main_worker",self.device_worker_class,{'board_number':self.board_number, 'num_DO': self.num_DO})
        self.primary_worker = "main_worker"
        
        # Set the capabilities of this device
        self.supports_smart_programming(True) 
        
        ####
        #### TODO: FIX
        ####
        # Status monitor timout
        self.statemachine_timeout_add(2000, self.status_monitor)
        
        # Default values for status prior to the status monitor first running:
        self.status = {'stopped':False,'reset':False,'running':False, 'waiting':False}
        
        # Get status widgets
        # self.status_widgets = {'stopped_yes':self.builder.get_object('stopped_yes'),
                               # 'stopped_no':self.builder.get_object('stopped_no'),
                               # 'reset_yes':self.builder.get_object('reset_yes'),
                               # 'reset_no':self.builder.get_object('reset_no'),
                               # 'running_yes':self.builder.get_object('running_yes'),
                               # 'running_no':self.builder.get_object('running_no'),
                               # 'waiting_yes':self.builder.get_object('waiting_yes'),
                               # 'waiting_no':self.builder.get_object('waiting_no')}
        
        

   
    
    # This function gets the status of the Pulseblaster from the spinapi,
    # and updates the front panel widgets!
    @define_state(MODE_MANUAL|MODE_BUFFERED|MODE_TRANSITION_TO_BUFFERED|MODE_TRANSITION_TO_MANUAL,True)  
    def status_monitor(self,notify_queue=None):
        # When called with a queue, this function writes to the queue
        # when the pulseblaster is waiting. This indicates the end of
        # an experimental run.
        self.status, waits_pending = yield(self.queue_work(self._primary_worker,'check_status'))
        
        if notify_queue is not None and self.status['waiting'] and not waits_pending:
            # Experiment is over. Tell the queue manager about it, then
            # set the status checking timeout back to every 2 seconds
            # with no queue.
            notify_queue.put('done')
            self.statemachine_timeout_remove(self.status_monitor)
            self.statemachine_timeout_add(2000,self.status_monitor)
        
        # TODO: Update widgets
        # a = ['stopped','reset','running','waiting']
        # for name in a:
            # if self.status[name] == True:
                # self.status_widgets[name+'_no'].hide()
                # self.status_widgets[name+'_yes'].show()
            # else:                
                # self.status_widgets[name+'_no'].show()
                # self.status_widgets[name+'_yes'].hide()
        
    
    @define_state(MODE_MANUAL|MODE_BUFFERED|MODE_TRANSITION_TO_BUFFERED|MODE_TRANSITION_TO_MANUAL,True)  
    def start(self,widget=None):
        yield(self.queue_work(self._primary_worker,'pb_start'))
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

@BLACS_worker        
class PulseblasterNoDDSWorker(Worker):
    core_clock_freq = 100
    def init(self):
        exec 'from spinapi import *' in globals()
        import spinapi
        version = [int(v) for v in spinapi.__version__.split('-')[0].split('.')]
        requires_version = (3,0,4)
        try:
            assert version[0] == requires_version[0]
            assert version[1] >= requires_version[1]
            assert version[2] >= requires_version[2]
        except AssertionError:
            raise ImportError('This PulseBlaster requires at least Python spinapi v%d.%d.%d'%requires_version)
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
        
    def transition_to_buffered(self,device_name,h5file,initial_values,fresh):
        self.h5file = h5file
        with h5py.File(h5file,'r') as hdf5_file:
            group = hdf5_file['devices/%s'%device_name]
                           
            # Now for the pulse program:
            pulse_program = group['PULSE_PROGRAM'][2:]
            
            #Let's get the final state of the pulseblaster. z's are the args we don't need:
            flags,z,z,z = pulse_program[-1]
            
            if fresh or (self.smart_cache['initial_values'] != initial_values) or \
            (len(self.smart_cache['pulse_program']) != len(pulse_program)) or \
            (self.smart_cache['pulse_program'] != pulse_program).any() or \
            not self.smart_cache['ready_to_go']:
            
                self.smart_cache['ready_to_go'] = True
                self.smart_cache['initial_values'] = initial_values
                pb_start_programming(PULSE_PROGRAM)
                # Line zero is a wait on the final state of the program:
                pb_inst_pbonly(flags,WAIT,0,100)
                
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
                # Line one is a continue with the current front panel values:
                pb_inst_pbonly(initial_flags, CONTINUE, 0, 100)
                # Now the rest of the program:
                if fresh or len(self.smart_cache['pulse_program']) != len(pulse_program) or \
                (self.smart_cache['pulse_program'] != pulse_program).any():
                    self.smart_cache['pulse_program'] = pulse_program
                    for args in pulse_program:
                        pb_inst_pbonly(*args)
                pb_stop_programming()
            
            # Are there waits in use in this experiment? The monitor waiting for the end of
            # the experiment will need to know:
            self.waits_pending =  bool(len(hdf5_file['waits']))
            
            # Now we build a dictionary of the final state to send back to the GUI:
            return_values = {}
            # Since we are converting from an integer to a binary string, we need to reverse the string! (see notes above when we create flags variables)
            return_flags = bin(flags)[2:].rjust(self.num_DO,'0')[::-1]
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
        return pb_read_status(), self.waits_pending

    def transition_to_manual(self):
        status, waits_pending = self.check_status()
        if status['waiting'] and not waits_pending:
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
        


