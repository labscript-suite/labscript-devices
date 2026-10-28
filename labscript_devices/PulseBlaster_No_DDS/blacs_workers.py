#####################################################################
#                                                                   #
# /labscript_devices/PulseBlaster_No_DDS/blacs_workers.py           #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from blacs.tab_base_classes import Worker


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
            
            if fresh or (self.smart_cache['initial_values'] != initial_values) or \
                (len(self.smart_cache['pulse_program']) != len(pulse_program)) or \
                (self.smart_cache['pulse_program'] != pulse_program).any() or \
                not self.smart_cache['ready_to_go']:
                # Enter programming mode
                pb_start_programming(PULSE_PROGRAM)
            
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
                    
            elif self.programming_scheme == 'pb_stop_programming/STOP':
                # Ensure start_programming called if the programming_scheme is 'pb_stop_programming/STOP'
                # so we are ready to be triggered by a call to pb_stop_programming() 
                # even if no programming occurred due to smart programming:
                pb_start_programming(PULSE_PROGRAM)
            
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
