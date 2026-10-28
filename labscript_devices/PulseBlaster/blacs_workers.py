#####################################################################
#                                                                   #
# /labscript_devices/PulseBlaster/blacs_workers.py                  #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################
from blacs.tab_base_classes import Worker


class PulseblasterWorker(Worker):
    def init(self):
        exec('from spinapi import *', globals())
        global h5py; import labscript_utils.h5_lock, h5py
        global zprocess; import zprocess
        
        self.pb_start = pb_start
        self.pb_stop = pb_stop
        self.pb_reset = pb_reset
        self.pb_close = pb_close
        self.pb_read_status = pb_read_status
        self.smart_cache = {'amps0':None,'freqs0':None,'phases0':None,
                            'amps1':None,'freqs1':None,'phases1':None,
                            'pulse_program':None,'ready_to_go':False,
                            'initial_values':None}
                            
        # An event for checking when all waits (if any) have completed, so that
        # we can tell the difference between a wait and the end of an experiment.
        # The wait monitor device is expected to post such events, which we'll wait on:
        self.all_waits_finished = zprocess.Event('all_waits_finished')
        self.waits_pending = False
    
        pb_select_board(self.board_number)
        pb_init()
        pb_core_clock(75)
        
        # This is only set to True on a per-shot basis, so set it to False
        # for manual mode. Set associated attributes to None:
        self.time_based_stop_workaround = False
        self.time_based_shot_duration = None
        self.time_based_shot_end_time = None

    def program_manual(self,values):
    
        if self.programming_scheme == 'pb_stop_programming/STOP':
            # Need to ensure device is stopped before programming - or we won't know what line it's on.
            pb_stop()
            
        # Program the DDS registers:
        for i in range(2):
            pb_select_dds(i)
            # Program the frequency, amplitude and phase into their
            # zeroth registers:
            program_amp_regs(values['dds %d'%i]['amp']) # Does not call pb_stop_programming anyway, so no kwarg needed
            program_freq_regs(values['dds %d'%i]['freq']/10.0**6, call_stop_programming=False) # method expects MHz
            program_phase_regs(values['dds %d'%i]['phase'], call_stop_programming=False)

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
        for i in range(12):
            if values['flag %d'%i]:
                flags += '1'
            else:
                flags += '0'
        
        # Write the first two lines of the pulse program:
        pb_start_programming(PULSE_PROGRAM)
        # Line zero is a wait:
        pb_inst_dds2(0,0,0,values['dds 0']['gate'],0,0,0,0,values['dds 1']['gate'],0,flags, WAIT, 0, 100)
        # Line one is a brach to line 0:
        pb_inst_dds2(0,0,0,values['dds 0']['gate'],0,0,0,0,values['dds 1']['gate'],0,flags, BRANCH, 0, 100)
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
            
            # Program the DDS registers:
            ampregs = []
            freqregs = []
            phaseregs = []
            for i in range(2):
                amps = group['DDS%d/AMP_REGS'%i][:]
                freqs = group['DDS%d/FREQ_REGS'%i][:]
                phases = group['DDS%d/PHASE_REGS'%i][:]
                
                amps[0] = initial_values['dds %d'%i]['amp']
                freqs[0] = initial_values['dds %d'%i]['freq']/10.0**6 # had better be in MHz!
                phases[0] = initial_values['dds %d'%i]['phase']
                
                pb_select_dds(i)
                # Only reprogram each thing if there's been a change:
                if fresh or len(amps) != len(self.smart_cache['amps%d'%i]) or (amps != self.smart_cache['amps%d'%i]).any():   
                    self.smart_cache['amps%d'%i] = amps
                    program_amp_regs(*amps)
                if fresh or len(freqs) != len(self.smart_cache['freqs%d'%i]) or (freqs != self.smart_cache['freqs%d'%i]).any():
                    self.smart_cache['freqs%d'%i] = freqs
                    # We must be careful not to call stop_programming() until the end,
                    # lest the pulseblaster become responsive to triggers before we are done programming.
                    # This is not an issue for program_amp_regs above, only for freq and phase regs.
                    program_freq_regs(*freqs, call_stop_programming=False)
                if fresh or len(phases) != len(self.smart_cache['phases%d'%i]) or (phases != self.smart_cache['phases%d'%i]).any():      
                    self.smart_cache['phases%d'%i] = phases
                    # See above comment - we must not call pb_stop_programming here:
                    program_phase_regs(*phases, call_stop_programming=False)
                
                ampregs.append(amps)
                freqregs.append(freqs)
                phaseregs.append(phases)
                
            # Now for the pulse program:
            pulse_program = group['PULSE_PROGRAM'][2:]
            
            #Let's get the final state of the pulseblaster. z's are the args we don't need:
            freqreg0,phasereg0,ampreg0,en0,z,freqreg1,phasereg1,ampreg1,en1,z,flags,z,z,z = pulse_program[-1]
            finalfreq0 = freqregs[0][freqreg0]*10.0**6 # Front panel expects frequency in Hz
            finalfreq1 = freqregs[1][freqreg1]*10.0**6 # Front panel expects frequency in Hz
            finalamp0 = ampregs[0][ampreg0]
            finalamp1 = ampregs[1][ampreg1]
            finalphase0 = phaseregs[0][phasereg0]
            finalphase1 = phaseregs[1][phasereg1]
            
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
                for i in range(12):
                    if initial_values['flag %d'%i]:
                        initial_flags += '1'
                    else:
                        initial_flags += '0'

                if self.programming_scheme == 'pb_start/BRANCH':
                    # Line zero is a wait on the final state of the program in 'pb_start/BRANCH' mode 
                    pb_inst_dds2(freqreg0,phasereg0,ampreg0,en0,0,freqreg1,phasereg1,ampreg1,en1,0,flags,WAIT,0,100)
                else:
                    # Line zero otherwise just contains the initial state 
                    pb_inst_dds2(0,0,0,initial_values['dds 0']['gate'],0,0,0,0,initial_values['dds 1']['gate'],0,initial_flags, CONTINUE, 0, 100)

                # Line one is a continue with the current front panel values:
                pb_inst_dds2(0,0,0,initial_values['dds 0']['gate'],0,0,0,0,initial_values['dds 1']['gate'],0,initial_flags, CONTINUE, 0, 100)
                # Now the rest of the program:
                if fresh or len(self.smart_cache['pulse_program']) != len(pulse_program) or \
                (self.smart_cache['pulse_program'] != pulse_program).any():
                    self.smart_cache['pulse_program'] = pulse_program
                    for args in pulse_program:
                        pb_inst_dds2(*args)
            
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
                # Having waits but not a wait monitor means we can't tell when the shot
                # is over unless the shot ends in a STOP instruction:
                assert self.programming_scheme == 'pb_stop_programming/STOP'

            # Now we build a dictionary of the final state to send back to the GUI:
            return_values = {'dds 0':{'freq':finalfreq0, 'amp':finalamp0, 'phase':finalphase0, 'gate':en0},
                             'dds 1':{'freq':finalfreq1, 'amp':finalamp1, 'phase':finalphase1, 'gate':en1},
                            }
            # Since we are converting from an integer to a binary string, we need to reverse the string! (see notes above when we create flags variables)
            return_flags = str(bin(flags)[2:]).rjust(12,'0')[::-1]
            for i in range(12):
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
