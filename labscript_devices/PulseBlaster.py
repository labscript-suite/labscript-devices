#####################################################################
#                                                                   #
# /PulseBlaster.py                                                  #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################

from labscript_devices import BLACS_tab, runviewer_parser
from labscript_utils import dedent

from labscript import (
    Device,
    PseudoclockDevice,
    Pseudoclock,
    ClockLine,
    IntermediateDevice,
    DigitalQuantity,
    DigitalOut,
    DDS,
    DDSQuantity,
    config,
    LabscriptError,
    set_passed_properties,
    compiler,
)

import numpy as np

import labscript_utils.h5_lock, h5py

import time

class PulseBlasterDDS(DDSQuantity):
    description = 'PulseBlasterDDS'
    def __init__(self, *args, **kwargs):
        if 'call_parents_add_device' in kwargs:
            call_parents_add_device = kwargs['call_parents_add_device']
        else:
            call_parents_add_device = True

        kwargs['call_parents_add_device'] = False
        DDSQuantity.__init__(self, *args, **kwargs)

        self.gate = DigitalQuantity(self.name + '_gate', self, 'gate')
        self.phase_reset = DigitalQuantity(self.name + '_phase_reset', self, 'phase_reset')

        if call_parents_add_device:
            self.parent_device.add_device(self)

    def hold_phase(self, t):
        self.phase_reset.go_high(t)

    def release_phase(self, t):
        self.phase_reset.go_low(t)


profiles = {}
def profile(funct):
    func = funct.__name__
    if func not in profiles:
        profiles[func] = {'total_time':0, 'min':None, 'max':0, 'num_calls':0, 'average_time_per_call':0}
    
    def new_func(*args,**kwargs):
        start_time = time.time()
        ret = funct(*args,**kwargs)
        runtime = time.time()-start_time
        profiles[func]['total_time'] += runtime
        profiles[func]['num_calls'] += 1
        profiles[func]['min'] = profiles[func]['min'] if profiles[func]['min'] is not None and profiles[func]['min'] < runtime else runtime
        profiles[func]['max'] = profiles[func]['max'] if profiles[func]['max'] > runtime else runtime
        profiles[func]['average_time_per_call'] = profiles[func]['total_time']/profiles[func]['num_calls']
        
        return ret
    # return new_func
    return funct
    
def start_profile(name):
    if name not in profiles:
        profiles[name] = {'total_time':0, 'min':None, 'max':0, 'num_calls':0, 'average_time_per_call':0}
        
    if 'start_time' in profiles[name]:
        raise Exception('You cannot call start_profile for %s without first calling stop_profile'%name)
        
    profiles[name]['start_time'] = time.time()
    
def stop_profile(name):
    if name not in profiles or 'start_time' not in profiles[name]:
        raise Exception('You must first call start_profile for %s before calling stop_profile')
        
    runtime = time.time()-profiles[name]['start_time']
    del profiles[name]['start_time']
    profiles[name]['total_time'] += runtime
    profiles[name]['num_calls'] += 1
    profiles[name]['min'] = profiles[name]['min'] if profiles[name]['min'] is not None and profiles[name]['min'] < runtime else runtime
    profiles[name]['max'] = profiles[name]['max'] if profiles[name]['max'] > runtime else runtime
    profiles[name]['average_time_per_call'] = profiles[name]['total_time']/profiles[name]['num_calls']


class PulseBlaster(PseudoclockDevice):
    
    pb_instructions = {'CONTINUE':   0,
                       'STOP':       1, 
                       'LOOP':       2, 
                       'END_LOOP':   3,
                       'BRANCH':     6,
                       'LONG_DELAY': 7,
                       'WAIT':       8}
                       
    description = 'PB-DDSII-300'
    clock_limit = 8.3e6 # Slight underestimate I think.
    clock_resolution = 26.6666666666666666e-9
    # TODO: Add n_dds and generalise code
    n_flags = 12
    
    core_clock_freq = 75 # MHz
    # This value is coupled to a value in the PulseBlaster worker process of BLACS
    # This number was found experimentally but is determined theoretically by the
    # instruction lengths in BLACS, and a finite delay in the PulseBlaster
    #
    # IF YOU CHANGE ONE, YOU MUST CHANGE THE OTHER!
    trigger_delay = 250e-9 
    wait_delay = 100e-9
    trigger_edge_type = 'falling'
    
    # This device can only have Pseudoclock children (digital outs and DDS outputs should be connected to a child device)
    allowed_children = [Pseudoclock]
    
    @set_passed_properties(
        property_names = {"connection_table_properties": ["firmware",  "programming_scheme"],
                          "device_properties": ["pulse_width", "max_instructions",
                                                "time_based_stop_workaround",
                                                "time_based_stop_workaround_extra_time"]}
        )
    def __init__(self, name, trigger_device=None, trigger_connection=None, board_number=0, firmware = '',
                 programming_scheme='pb_start/BRANCH', pulse_width='symmetric', max_instructions=4000,
                 time_based_stop_workaround=False, time_based_stop_workaround_extra_time=0.5, **kwargs):
        PseudoclockDevice.__init__(self, name, trigger_device, trigger_connection, **kwargs)
        self.BLACS_connection = board_number
        # TODO: Implement capability checks based on firmware revision of PulseBlaster
        self.firmware_version = firmware
        
        # time_based_stop_workaround is for old pulseblaster models which do
        # not respond correctly to status checks. These models provide no way
        # to know when the shot has completed. So if
        # time_based_stop_workaround=True, we fall back to simply waiting
        # until stop_time (plus the timeout of all waits) and assuming in the
        # BLACS worker that the end of the shot occurs at this time.
        # time_based_stop_workaround_extra_time is a configurable duration for
        # how much longer than stop_time we should wait, to allow for software
        # timing variation. Note that since the maximum duration of all waits
        # is included in the calculation of the time at which the experiemnt
        # should be stopped, attention should be paid to the timeout argument
        # of all waits, since if it is larger than necessary, this will
        # increase the duration of your shots even if the waits are actually
        # short in duration.
        
        
        # If we are the master pseudoclock, there are two ways we can start and stop the PulseBlaster.
        #
        # 'pb_start/BRANCH':
        # Call pb_start(), to start us in software time. At the end of the program BRANCH to
        # a WAIT instruction at the beginning, ready to start again.
        #
        # 'pb_stop_programming/STOP'
        # Defer calling pb_stop_programming() until everything is ready to start.
        # Then, the next hardware trigger to the PulseBlaster will start it.
        # It is important not to call pb_stop_programming() too soon, because if the PulseBlaster is receiving
        # repeated triggers (such as from a 50/60-Hz line trigger), then we do not want it to start running
        # before everything is ready. Not calling pb_stop_programming() until we are ready ensures triggers are
        # ignored until then. In this case, we end with a STOP instruction, ensuring further triggers do not cause
        # the PulseBlaster to run repeatedly until start_programming()/stop_programming() are called once more.
        # The programming scheme is saved as a property in the connection table and read out by BLACS.
        possible_programming_schemes = ['pb_start/BRANCH', 'pb_stop_programming/STOP']
        if programming_scheme not in possible_programming_schemes:
            raise LabscriptError('programming_scheme must be one of %s'%str(possible_programming_schemes))
        if trigger_device is not None and programming_scheme != 'pb_start/BRANCH':
            raise LabscriptError('only the master pseudoclock can use a programming scheme other than \'pb_start/BRANCH\'')
        self.programming_scheme = programming_scheme

        # This is the minimum duration of a pulseblaster instruction. We save this now
        # because clock_limit will be modified to reflect child device limitations and
        # other things, but this remains the minimum instruction delay regardless of all
        # that.
        self.min_delay = 0.5 / self.clock_limit

        # For pulseblaster instructions lasting longer than the below duration, we will
        # instead use some multiple of the below, and then a regular instruction for the
        # remainder. The max instruction length of a pulseblaster is actually 2**32
        # clock cycles, but we subtract the minimum delay so that if the remainder is
        # less than the minimum instruction length, we can add self.long_delay to it (and
        # reduce the number of repetitions of the long delay by one), to keep it above
        # the minimum delay without exceeding the true maximum delay.
        self.long_delay = 2**32 / (self.core_clock_freq * 1e6) - self.min_delay

        if pulse_width == 'minimum':
            pulse_width = 0.5/self.clock_limit # the shortest possible
        elif pulse_width != 'symmetric':
            if not isinstance(pulse_width, (float, int, np.integer)):
                msg = ("pulse_width must be 'symmetric', 'minimum', or a number " +
                       "specifying a fixed pulse width to be used for clocking signals")
                raise ValueError(msg)

            if pulse_width < 0.5/self.clock_limit:
                message = ('pulse_width cannot be less than 0.5/%s.clock_limit '%self.__class__.__name__ +
                           '( = %s seconds)'%str(0.5/self.clock_limit))
                raise LabscriptError(message)
            # Round pulse width up to the nearest multiple of clock resolution:
            quantised_pulse_width = 2*pulse_width/self.clock_resolution
            quantised_pulse_width = int(quantised_pulse_width) + 1 # ceil(quantised_pulse_width)
            # This will be used as the high time of clock ticks:
            pulse_width = quantised_pulse_width*self.clock_resolution/2
            # This pulse width, if larger than the minimum, may limit how fast we can tick.
            # Update self.clock_limit accordingly.
            minimum_low_time = 0.5/self.clock_limit
            if pulse_width > minimum_low_time:
                self.clock_limit = 1/(pulse_width + minimum_low_time)
        self.pulse_width = pulse_width
        self.max_instructions = max_instructions

        # Create the internal pseudoclock
        self._pseudoclock = Pseudoclock('%s_pseudoclock'%name, self, 'clock') # possibly a better connection name than 'clock'?
        # Create the internal direct output clock_line
        self._direct_output_clock_line = ClockLine('%s_direct_output_clock_line'%name, self.pseudoclock, 'internal', ramping_allowed = False)
        # Create the internal intermediate device connected to the above clock line
        # This will have the direct DigitalOuts of DDSs of the PulseBlaster connected to it
        self._direct_output_device = PulseBlasterDirectOutputs('%s_direct_output_device'%name, self._direct_output_clock_line)
    
    @property
    def pseudoclock(self):
        return self._pseudoclock
        
    @property
    def direct_outputs(self):
        return self._direct_output_device
    
    def add_device(self, device):
        if not self.child_devices and isinstance(device, Pseudoclock):
            PseudoclockDevice.add_device(self, device)
            
        elif isinstance(device, Pseudoclock):
            raise LabscriptError('The %s %s automatically creates a Pseudoclock because it only supports one. '%(self.description, self.name) +
                                 'Instead of instantiating your own Pseudoclock object, please use the internal' +
                                 ' one stored in %s.pseudoclock'%self.name)
        elif isinstance(device, DDS) or isinstance(device, PulseBlasterDDS) or isinstance(device, DigitalOut):
            #TODO: Defensive programming: device.name may not exist!
            raise LabscriptError('You have connected %s directly to %s, which is not allowed. You should instead specify the parent_device of %s as %s.direct_outputs'%(device.name, self.name, device.name, self.name))
        else:
            raise LabscriptError('You have connected %s (class %s) to %s, but %s does not support children with that class.'%(device.name, device.__class__, self.name, self.name))
                
    def flag_valid(self, flag):
        if -1 < flag < self.n_flags:
            return True
        return False     
        
    def flag_is_clock(self, flag):
        for clock_line in self.pseudoclock.child_devices:
            if clock_line.connection == 'internal': #ignore internal clockline
                continue
            if flag == self.get_flag_number(clock_line.connection):
                return True
        return False
            
    def get_flag_number(self, connection):
        # TODO: Error checking
        prefix, connection = connection.split()
        return int(connection)
    
    def get_direct_outputs(self):
        """Finds out which outputs are directly attached to the PulseBlaster"""
        dig_outputs = []
        dds_outputs = []
        for output in self.direct_outputs.get_all_outputs():
            # If we are a child of a DDS
            if isinstance(output.parent_device, DDS) or isinstance(output.parent_device, PulseBlasterDDS):
                # and that DDS has not been processed yet
                if output.parent_device not in dds_outputs:
                    # process the DDS instead of the child
                    output = output.parent_device
                else:
                    # ignore the child
                    continue
            
            # only check DDS and DigitalOuts (so ignore the children of the DDS)
            if isinstance(output,DDS) or isinstance(output,PulseBlasterDDS) or isinstance(output, DigitalOut):
                # get connection number and prefix
                try:
                    prefix, connection = output.connection.split()
                    assert prefix == 'flag' or prefix == 'dds'
                    connection = int(connection)
                except:
                    raise LabscriptError('%s %s has invalid connection string: \'%s\'. '%(output.description,output.name,str(output.connection)) + 
                                         'Format must be \'flag n\' with n an integer less than %d, or \'dds n\' with n less than 2.'%self.n_flags)
                # run checks on the connection string to make sure it is valid
                # TODO: Most of this should be done in add_device() No?
                if prefix == 'flag' and not self.flag_valid(connection):
                    raise LabscriptError('%s is set as connected to flag %d of %s. '%(output.name, connection, self.name) +
                                         'Output flag number must be a integer from 0 to %d.'%(self.n_flags-1))
                if prefix == 'flag' and self.flag_is_clock(connection):
                    raise LabscriptError('%s is set as connected to flag %d of %s.'%(output.name, connection, self.name) +
                                         ' This flag is already in use as one of the PulseBlaster\'s clock flags.')                         
                if prefix == 'dds' and not connection < 2:
                    raise LabscriptError('%s is set as connected to output connection %d of %s. '%(output.name, connection, self.name) +
                                         'DDS output connection number must be a integer less than 2.')
                
                # Check that the connection string doesn't conflict with another output
                for other_output in dig_outputs + dds_outputs:
                    if output.connection == other_output.connection:
                        raise LabscriptError('%s and %s are both set as connected to %s of %s.'%(output.name, other_output.name, output.connection, self.name))
                
                # store a reference to the output
                if isinstance(output, DigitalOut):
                    dig_outputs.append(output)
                elif isinstance(output, DDS) or isinstance(output, PulseBlasterDDS):
                    dds_outputs.append(output)
                
        return dig_outputs, dds_outputs

    def generate_registers(self, hdf5_file, dds_outputs):
        ampdicts = {}
        phasedicts = {}
        freqdicts = {}
        group = hdf5_file['/devices/'+self.name]
        dds_dict = {}
        for output in dds_outputs:
            num = int(output.connection.split()[1])
            dds_dict[num] = output
        for num in [0,1]:
            
            if num in dds_dict:
                output = dds_dict[num]
            
                # Ensure that amplitudes are within bounds:
                if any(output.amplitude.raw_output > 1)  or any(output.amplitude.raw_output < 0):
                    raise LabscriptError('%s %s '%(output.amplitude.description, output.amplitude.name) +
                                      'can only have values between 0 and 1, ' + 
                                      'the limit imposed by %s.'%output.name)
                                      
                # Ensure that frequencies are within bounds:
                if any(output.frequency.raw_output > 150e6 )  or any(output.frequency.raw_output < 0):
                    raise LabscriptError('%s %s '%(output.frequency.description, output.frequency.name) +
                                      'can only have values between 0Hz and and 150MHz, ' + 
                                      'the limit imposed by %s.'%output.name)
                                      
                # Ensure that phase wraps around:
                output.phase.raw_output %= 360
                
                amps = set(output.amplitude.raw_output)
                phases = set(output.phase.raw_output)
                freqs = set(output.frequency.raw_output)
            else:
                # If the DDS is unused, it will use the following values
                # for the whole experimental run:
                amps = set([0])
                phases = set([0])
                freqs = set([0])
                                  
            if len(amps) > 1024:
                raise LabscriptError('%s dds%d can only support 1024 amplitude registers, and %s have been requested.'%(self.name, num, str(len(amps))))
            if len(phases) > 128:
                raise LabscriptError('%s dds%d can only support 128 phase registers, and %s have been requested.'%(self.name, num, str(len(phases))))
            if len(freqs) > 1024:
                raise LabscriptError('%s dds%d can only support 1024 frequency registers, and %s have been requested.'%(self.name, num, str(len(freqs))))
                                
            # start counting at 1 to leave room for the dummy instruction,
            # which BLACS will fill in with the state of the front
            # panel:
            ampregs = range(1,len(amps)+1)
            freqregs = range(1,len(freqs)+1)
            phaseregs = range(1,len(phases)+1)
            
            ampdicts[num] = dict(zip(amps,ampregs))
            freqdicts[num] = dict(zip(freqs,freqregs))
            phasedicts[num] = dict(zip(phases,phaseregs))
            
            # The zeros are the dummy instructions:
            freq_table = np.array([0] + list(freqs), dtype = np.float64) / 1e6 # convert to MHz
            amp_table = np.array([0] + list(amps), dtype = np.float32)
            phase_table = np.array([0] + list(phases), dtype = np.float64)
            
            subgroup = group.create_group('DDS%d'%num)
            subgroup.create_dataset('FREQ_REGS', compression=config.compression, data = freq_table)
            subgroup.create_dataset('AMP_REGS', compression=config.compression, data = amp_table)
            subgroup.create_dataset('PHASE_REGS', compression=config.compression, data = phase_table)
            
        return freqdicts, ampdicts, phasedicts
        
    def convert_to_pb_inst(self, dig_outputs, dds_outputs, freqs, amps, phases):
        pb_inst = []
        
        # index to keep track of where in output.raw_output the
        # pulseblaster flags are coming from
        # starts at -1 because the internal flag should always tick on the first instruction and be 
        # incremented (to 0) before it is used to index any arrays
        i = -1 
        # index to record what line number of the pulseblaster hardware
        # instructions we're up to:
        j = 0
        # We've delegated the initial two instructions off to BLACS, which
        # can ensure continuity with the state of the front panel. Thus
        # these two instructions don't actually do anything:
        flags = [0]*self.n_flags
        freqregs = [0]*2
        ampregs = [0]*2
        phaseregs = [0]*2
        dds_enables = [0]*2
        phase_resets = [0]*2
        
        pb_inst.append({'freqs': freqregs, 'amps': ampregs, 'phases': phaseregs, 'enables':dds_enables, 'phase_resets': phase_resets,
                        'flags': ''.join([str(flag) for flag in flags]), 'instruction': 'STOP',
                        'data': 0, 'delay': 10.0/self.clock_limit*1e9})
        pb_inst.append({'freqs': freqregs, 'amps': ampregs, 'phases': phaseregs, 'enables':dds_enables, 'phase_resets': phase_resets,
                        'flags': ''.join([str(flag) for flag in flags]), 'instruction': 'STOP',
                        'data': 0, 'delay': 10.0/self.clock_limit*1e9})    
        j += 2
        
        flagstring = '0'*self.n_flags # So that this variable is still defined if the for loop has no iterations
        for k, instruction in enumerate(self.pseudoclock.clock):
            if instruction == 'WAIT':
                # This is a wait instruction. Repeat the last instruction but with a 100ns delay and a WAIT op code:
                wait_instruction = pb_inst[-1].copy()
                wait_instruction['delay'] = 100
                wait_instruction['instruction'] = 'WAIT'
                wait_instruction['data'] = 0
                pb_inst.append(wait_instruction)
                j += 1
                continue
                
            flags = [0]*self.n_flags
            # The registers below are ones, not zeros, so that we don't
            # use the BLACS-inserted initial instructions. Instead
            # unused DDSs have a 'zero' in register one for freq, amp
            # and phase.
            freqregs = [1]*2
            ampregs = [1]*2
            phaseregs = [1]*2
            dds_enables = [0]*2
            phase_resets = [0]*2
            
            # This flag indicates whether we need a full clock tick, or are just updating an internal output
            only_internal = True
            # find out which clock flags are ticking during this instruction
            for clock_line in instruction['enabled_clocks']:
                if clock_line == self._direct_output_clock_line: 
                    # advance i (the index keeping track of internal clockline output)
                    i += 1
                else:
                    flag_index = int(clock_line.connection.split()[1])
                    flags[flag_index] = 1
                    # We are not just using the internal clock line
                    only_internal = False
            
            for output in dig_outputs:
                flagindex = int(output.connection.split()[1])
                flags[flagindex] = int(output.raw_output[i])
            for output in dds_outputs:
                ddsnumber = int(output.connection.split()[1])
                freqregs[ddsnumber] = freqs[ddsnumber][output.frequency.raw_output[i]]
                ampregs[ddsnumber] = amps[ddsnumber][output.amplitude.raw_output[i]]
                phaseregs[ddsnumber] = phases[ddsnumber][output.phase.raw_output[i]]
                dds_enables[ddsnumber] = output.gate.raw_output[i]
                if isinstance(output, PulseBlasterDDS):
                    phase_resets[ddsnumber] = output.phase_reset.raw_output[i]
                
            flagstring = ''.join([str(flag) for flag in flags])
            
            if instruction['reps'] > 1048576:
                raise LabscriptError('Pulseblaster cannot support more than 1048576 loop iterations. ' +
                                      str(instruction['reps']) +' were requested at t = ' + str(instruction['start']) + '. '+
                                     'This can be fixed easily enough by using nested loops. If it is needed, ' +
                                     'please file a feature request at' +
                                     'http://redmine.physics.monash.edu.au/projects/labscript.')
                
            if not only_internal:
                if self.pulse_width == 'symmetric':
                    high_time = instruction['step']/2
                else:
                    high_time = self.pulse_width
                # High time cannot be longer than self.long_delay (~57 seconds for a
                # 75MHz core clock freq). If it is, clip it to self.long_delay. In this
                # case we are not honouring the requested symmetric or fixed pulse
                # width. To do so would be possible, but would consume more pulseblaster
                # instructions, so we err on the side of fewer instructions:
                high_time = min(high_time, self.long_delay)

                # Low time is whatever is left:
                low_time = instruction['step'] - high_time

                # Do we need to insert a LONG_DELAY instruction to create a delay this
                # long?
                n_long_delays, remaining_low_time =  divmod(low_time, self.long_delay)

                # If the remainder is too short to be output, add self.long_delay to it.
                # self.long_delay was constructed such that adding self.min_delay to it
                # is still not too long for a single instruction:
                if n_long_delays and remaining_low_time < self.min_delay:
                    n_long_delays -= 1
                    remaining_low_time += self.long_delay

                # The start loop instruction, Clock edges are high:
                pb_inst.append({'freqs': freqregs, 'amps': ampregs, 'phases': phaseregs, 'enables':dds_enables, 'phase_resets':phase_resets,
                                'flags': flagstring, 'instruction': 'LOOP',
                                'data': instruction['reps'], 'delay': high_time*1e9})
                
                for clock_line in instruction['enabled_clocks']:
                    if clock_line != self._direct_output_clock_line:
                        flag_index = int(clock_line.connection.split()[1])
                        flags[flag_index] = 0
                        
                flagstring = ''.join([str(flag) for flag in flags])
            
                # The long delay instruction, if any. Clock edges are low: 
                if n_long_delays:
                    pb_inst.append({'freqs': freqregs, 'amps': ampregs, 'phases': phaseregs, 'enables':dds_enables, 'phase_resets':phase_resets,
                                'flags': flagstring, 'instruction': 'LONG_DELAY',
                                'data': int(n_long_delays), 'delay': self.long_delay*1e9})
                                
                # Remaining low time. Clock edges are low:
                pb_inst.append({'freqs': freqregs, 'amps': ampregs, 'phases': phaseregs, 'enables':dds_enables, 'phase_resets':phase_resets,
                                'flags': flagstring, 'instruction': 'END_LOOP',
                                'data': j, 'delay': remaining_low_time*1e9})
                                
                # Two instructions were used in the case of there being no LONG_DELAY, 
                # otherwise three. This increment is done here so that the j referred
                # to in the previous line still refers to the LOOP instruction.
                j += 3 if n_long_delays else 2
            else:
                # We only need to update a direct output, so no need to tick the clocks.

                # Do we need to insert a LONG_DELAY instruction to create a delay this
                # long?
                n_long_delays, remaining_delay =  divmod(instruction['step'], self.long_delay)
                # If the remainder is too short to be output, add self.long_delay to it.
                # self.long_delay was constructed such that adding self.min_delay to it
                # is still not too long for a single instruction:
                if n_long_delays and remaining_delay < self.min_delay:
                    n_long_delays -= 1
                    remaining_delay += self.long_delay
                
                if n_long_delays:
                    pb_inst.append({'freqs': freqregs, 'amps': ampregs, 'phases': phaseregs, 'enables':dds_enables, 'phase_resets':phase_resets,
                                'flags': flagstring, 'instruction': 'LONG_DELAY',
                                'data': int(n_long_delays), 'delay': self.long_delay*1e9})

                pb_inst.append({'freqs': freqregs, 'amps': ampregs, 'phases': phaseregs, 'enables':dds_enables, 'phase_resets':phase_resets,
                                'flags': flagstring, 'instruction': 'CONTINUE',
                                'data': 0, 'delay': remaining_delay*1e9})
                
                j += 2 if n_long_delays else 1
                

        if self.programming_scheme == 'pb_start/BRANCH':
            # This is how we stop the pulse program. We branch from the last
            # instruction to the zeroth, which BLACS has programmed in with
            # the same values and a WAIT instruction. The PulseBlaster then
            # waits on instuction zero, which is a state ready for either
            # further static updates or buffered mode.
            pb_inst.append({'freqs': freqregs, 'amps': ampregs, 'phases': phaseregs, 'enables':dds_enables, 'phase_resets':phase_resets,
                            'flags': flagstring, 'instruction': 'BRANCH',
                            'data': 0, 'delay': 10.0/self.clock_limit*1e9})
        elif self.programming_scheme == 'pb_stop_programming/STOP':
            # An ordinary stop instruction. This has the downside that the PulseBlaster might
            # (on some models) reset its output to zero momentarily until BLACS calls program_manual, which
            # it will for this programming scheme. However it is necessary when the PulseBlaster has
            # repeated triggers coming to it, such as a 50Hz/60Hz line trigger. We can't have it sit
            # on a WAIT instruction as above, or it will trigger and run repeatedly when that's not what
            # we wanted.
            pb_inst.append({'freqs': freqregs, 'amps': ampregs, 'phases': phaseregs, 'enables':dds_enables, 'phase_resets':phase_resets,
                            'flags': flagstring, 'instruction': 'STOP',
                            'data': 0, 'delay': 10.0/self.clock_limit*1e9})
        else:
            raise AssertionError('Invalid programming scheme %s'%str(self.programming_scheme))
            
        if len(pb_inst) > self.max_instructions:
            raise LabscriptError("The Pulseblaster memory cannot store more than {:d} instuctions, but the PulseProgram contains {:d} instructions.".format(self.max_instructions, len(pb_inst))) 
            
        return pb_inst
        
    def write_pb_inst_to_h5(self, pb_inst, hdf5_file):
        # OK now we squeeze the instructions into a numpy array ready for writing to hdf5:
        pb_dtype = [('freq0', np.int32), ('phase0', np.int32), ('amp0', np.int32), 
                    ('dds_en0', np.int32), ('phase_reset0', np.int32),
                    ('freq1', np.int32), ('phase1', np.int32), ('amp1', np.int32),
                    ('dds_en1', np.int32), ('phase_reset1', np.int32),
                    ('flags', np.int32), ('inst', np.int32),
                    ('inst_data', np.int32), ('length', np.float64)]
        pb_inst_table = np.empty(len(pb_inst),dtype = pb_dtype)
        for i,inst in enumerate(pb_inst):
            flagint = int(inst['flags'][::-1],2)
            instructionint = self.pb_instructions[inst['instruction']]
            dataint = inst['data']
            delaydouble = inst['delay']
            freq0 = inst['freqs'][0]
            freq1 = inst['freqs'][1]
            phase0 = inst['phases'][0]
            phase1 = inst['phases'][1]
            amp0 = inst['amps'][0]
            amp1 = inst['amps'][1]
            en0 = inst['enables'][0]
            en1 = inst['enables'][1]
            phase_reset0 = inst['phase_resets'][0]
            phase_reset1 = inst['phase_resets'][1]
            
            pb_inst_table[i] = (freq0,phase0,amp0,en0,phase_reset0,freq1,phase1,amp1,en1,phase_reset1, flagint, 
                                instructionint, dataint, delaydouble)     
                                
        # Okay now write it to the file: 
        group = hdf5_file['/devices/'+self.name]  
        group.create_dataset('PULSE_PROGRAM', compression=config.compression,data = pb_inst_table)   
        self.set_property('stop_time', self.stop_time, location='device_properties')


    def _check_wait_monitor_ok(self):
        if (
            compiler.master_pseudoclock is self
            and compiler.wait_table
            and compiler.wait_monitor is None
            and self.programming_scheme != 'pb_stop_programming/STOP'
        ):
            msg = """If using waits without a wait monitor, the PulseBlaster used as a
                master pseudoclock must have
                programming_scheme='pb_stop_programming/STOP'. Otherwise there is no way
                for BLACS to distinguish between a wait, and the end of a shot. Either
                use a wait monitor (see labscript.WaitMonitor for details) or set
                programming_scheme='pb_stop_programming/STOP for %s."""
            raise LabscriptError(dedent(msg) % self.name)

    def generate_code(self, hdf5_file):
        # Generate the hardware instructions
        hdf5_file.create_group('/devices/' + self.name)
        PseudoclockDevice.generate_code(self, hdf5_file)
        dig_outputs, dds_outputs = self.get_direct_outputs()
        freqs, amps, phases = self.generate_registers(hdf5_file, dds_outputs)
        pb_inst = self.convert_to_pb_inst(dig_outputs, dds_outputs, freqs, amps, phases)
        self._check_wait_monitor_ok()
        self.write_pb_inst_to_h5(pb_inst, hdf5_file)
        



class PulseBlasterDirectOutputs(IntermediateDevice):
    allowed_children = [DDS, PulseBlasterDDS, DigitalOut]
    clock_limit = PulseBlaster.clock_limit
    description = 'PB-DDSII-300 Direct Outputs'
  
    def add_device(self, device):
        IntermediateDevice.add_device(self, device)
        if isinstance(device, DDS):
            # Check that the user has not specified another digital line as the gate for this DDS, that doesn't make sense.
            # Then instantiate a DigitalQuantity to keep track of gating.
            if device.gate is None:
                device.gate = DigitalQuantity(device.name + '_gate', device, 'gate')
            else:
                raise LabscriptError('You cannot specify a digital gate ' +
                                     'for a DDS connected to %s. '% (self.name) + 
                                     'The digital gate is always internal to the Pulseblaster.')


from blacs.tab_base_classes import Worker, define_state
from blacs.tab_base_classes import MODE_MANUAL, MODE_TRANSITION_TO_BUFFERED, MODE_TRANSITION_TO_MANUAL, MODE_BUFFERED  

from blacs.device_base_class import DeviceTab

from qtutils import UiLoader
import qtutils.icons
import os

# We can't import * from QtCore & QtGui, as one of them has a function called bin() which overrides the builtin, which is used in the pulseblaster worker
from qtutils.qt import QtCore
from qtutils.qt import QtGui

    

@BLACS_tab
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
        self.create_worker("main_worker",PulseblasterWorker,{'board_number':self.board_number,
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
      

            
@runviewer_parser
class PulseBlasterParser(object):
    num_dds = 2
    num_flags = 12
    
    def __init__(self, path, device):
        self.path = path
        self.name = device.name
        self.device = device
        
        # We create a lookup table for strings to be used later as dictionary keys.
        # This saves having to evaluate '%d'%i many many times, and makes the _add_pulse_program_row_to_traces method
        # significantly more efficient
        self.dds_strings = {}
        for i in range(self.num_dds):
            self.dds_strings[i] = {}
            self.dds_strings[i]['ddsfreq'] = 'dds %d_freq'%i
            self.dds_strings[i]['ddsamp'] = 'dds %d_amp'%i
            self.dds_strings[i]['ddsphase'] = 'dds %d_phase'%i
            self.dds_strings[i]['freq'] = 'freq%d'%i
            self.dds_strings[i]['amp'] = 'amp%d'%i
            self.dds_strings[i]['phase'] = 'phase%d'%i
            self.dds_strings[i]['dds_en'] = 'dds_en%d'%i
            
        self.flag_strings = {}
        self.flag_powers = {}
        
        for i in range(self.num_flags):
            self.flag_strings[i] = 'flag %d'%i
            self.flag_powers[i] = 2**i
        
            
        
    def get_traces(self, add_trace, parent=None):
        if parent is None:
            # we're the master pseudoclock, software triggered. So we don't have to worry about trigger delays, etc
            pass
            
        # get the pulse program
        with h5py.File(self.path, 'r') as f:
            pulse_program = f['devices/%s/PULSE_PROGRAM'%self.name][:]
            # slow_clock_flag = eval(f['devices/%s'%self.name].attrs['slow_clock'])
            dds = {}
            for i in range(self.num_dds):
                dds[i] = {}
                for reg in ['FREQ', 'AMP', 'PHASE']:
                    dds[i][reg] = f['devices/%s/DDS%d/%s_REGS'%(self.name, i, reg)][:]
        
        clock = []
        traces = {}
        for i in range(self.num_flags):
            traces['flag %d'%i] = []
        for i in range(self.num_dds):
            for sub_chnl in ['freq', 'amp', 'phase']:
                traces['dds %d_%s'%(i,sub_chnl)] = []   
        
        # now build the traces
        t = 0. if parent is None else PulseBlaster.trigger_delay # Offset by initial trigger of parent
        i = 0
        while i < len(pulse_program):
            # ignore the first 2 instructions, they are dummy instructions for BLACS
            if i < 2:
                i += 1
                continue
            
            row = pulse_program[i]
            
            if row['inst'] == 2: # Loop
                loops = int(row['inst_data'])
                
                buffer = {}
                j = i
                while loops > 0:
                    looping = True
                    while looping:
                        row = pulse_program[j]
                        # buffer the index of traces used for this instruction
                        # Cuts the runtime down by ~60%
                        # start_profile('loop_contents')
                        if j not in buffer:
                            clock.append(t)
                            self._add_pulse_program_row_to_traces(traces, row, dds)
                            buffer[j] = len(clock)-1
                        else:                            
                            clock.append(t)
                            self._add_pulse_program_row_from_buffer(traces, buffer[j])
                        # stop_profile('loop_contents')
                            
                        # start_profile('end_of_loop')
                        t+= row['length']*1.0e-9
                        
                        if row['inst'] == 3: # END_LOOP
                            looping = False
                            # print 'end loop. j=%d, t=%.7f'%(j,t)
                            j = int(row['inst_data']) if loops > 1 else j
                            # print 'setting j=%d'%j
                        else:
                            # print 'in loop. j=%d, t=%.7f'%(j,t)
                            j+=1
                        # stop_profile('end_of_loop')
                    loops -= 1
                    
                i = j
                # print 'i now %d'%i
                    
            else: # Continue
                if row['inst'] == 8: #WAIT
                    print('Wait at %.9f'%t)
                    pass
                clock.append(t)
                self._add_pulse_program_row_to_traces(traces,row,dds)
                t+= row['length']*1.0e-9
            
                if row['inst'] == 8 and parent is not None: #WAIT
                    #TODO: Offset next time by trigger delay is not master pseudoclock
                    t+= PulseBlaster.trigger_delay
                    
            
            i += 1            
                
        print('Stop time: %.9f'%t)
        # now put together the traces
        to_return = {}
        clock = np.array(clock, dtype=np.float64)
        for name, data in traces.items():
            to_return[name] = (clock, np.array(data))
            
        
        # if slow_clock_flag is not None:
            # to_return['slow clock'] = to_return['flag %d'%slow_clock_flag[0]]
            
        clocklines_and_triggers = {}
        for pseudoclock_name, pseudoclock in self.device.child_list.items():
            for clock_line_name, clock_line in pseudoclock.child_list.items():
                if clock_line.parent_port == 'internal':
                    parent_device_name = '%s.direct_outputs'%self.name
                    for internal_device_name, internal_device in clock_line.child_list.items():
                        for channel_name, channel in internal_device.child_list.items():
                            if channel.device_class == 'Trigger':
                                clocklines_and_triggers[channel_name] = to_return[channel.parent_port]
                                add_trace(channel_name, to_return[channel.parent_port], parent_device_name, channel.parent_port)
                            else:
                                if channel.device_class == 'DDS':
                                    for subchnl_name, subchnl in channel.child_list.items():
                                        connection = '%s_%s'%(channel.parent_port, subchnl.parent_port)
                                        if connection in to_return:
                                            add_trace(subchnl.name, to_return[connection], parent_device_name, connection)
                                else:
                                    add_trace(channel_name, to_return[channel.parent_port], parent_device_name, channel.parent_port)
                else:
                    clocklines_and_triggers[clock_line_name] = to_return[clock_line.parent_port]
                    add_trace(clock_line_name, to_return[clock_line.parent_port], self.name, clock_line.parent_port)
            
        return clocklines_and_triggers
    
    @profile
    def _add_pulse_program_row_from_buffer(self, traces, index):
        for i in range(self.num_flags):
            traces[self.flag_strings[i]].append(traces[self.flag_strings[i]][index])
            
        for i in range(self.num_dds):
            current_strings = self.dds_strings[i]
            traces[current_strings['ddsfreq']].append(traces[current_strings['ddsfreq']][index])
            traces[current_strings['ddsphase']].append(traces[current_strings['ddsphase']][index])
            traces[current_strings['ddsamp']].append(traces[current_strings['ddsamp']][index])
            
    @profile            
    def _add_pulse_program_row_to_traces(self, traces, row, dds, flags = None):
        # add flags
        if flags is None:
            flags = np.binary_repr(row['flags'],self.num_flags)[::-1]
        for i in range(self.num_flags):
            traces[self.flag_strings[i]].append(int(flags[i]))
        
        # Below block saved for history. This is much slower compared to what is below!
        # for i in range(self.num_dds):
            # traces['dds %d_freq'%i].append(dds[i]['FREQ'][row['freq%d'%i]])
            # traces['dds %d_phase'%i].append(dds[i]['PHASE'][row['phase%d'%i]])
            # amp = dds[i]['AMP'][row['amp%d'%i]] if row['dds_en%d'%i] else 0
            # traces['dds %d_amp'%i].append(amp)
            
       
        # note that we are looking up keys for the traces dictionary and row array in self.dds_strings
        # Doing this reduces the runtime (of the below block) by 25%
        for i in range(self.num_dds):
            # Note: This is done to reduce runtime (about 10%)
            current_strings = self.dds_strings[i]
            current_dds = dds[i]
            
            traces[current_strings['ddsfreq']].append(current_dds['FREQ'][row[current_strings['freq']]])
            traces[current_strings['ddsphase']].append(current_dds['PHASE'][row[current_strings['phase']]])
            # Note: Using the inline if statement reduces the runtime (of this for loop) by 50%
            amp = current_dds['AMP'][row[current_strings['amp']]] if row[current_strings['dds_en']] else 0
            traces[current_strings['ddsamp']].append(amp)
            
            
