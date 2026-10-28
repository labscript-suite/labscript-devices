#####################################################################
#                                                                   #
# /labscript_devices/PulseBlaster/labscript_devices.py              #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################
from labscript_utils import dedent
from labscript import (
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
    description = 'PB-DDSII-300 Direct Outputs'

    @property
    def clock_limit(self):
        """clock_limit of the parent PulseBlaster."""
        return self.pseudoclock_device.clock_limit

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
