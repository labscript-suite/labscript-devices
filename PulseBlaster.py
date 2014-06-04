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
from labscript_devices import RunviewerParser

from labscript import Device, PseudoClock, DigitalQuantity, DigitalOut, DDS, config, LabscriptError

import numpy as np

import labscript_utils.h5_lock, h5py

class x(object):
    pass

import time

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
          
          
class PulseBlaster(PseudoClock):
    
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
    fast_clock_flag = 0
    slow_clock_flag = 1
    clock_type = 'slow clock'
    n_flags = 12
    
    # This value is coupled to a value in the PulseBlaster worker process of BLACS
    # This number was found experimentally but is determined theoretically by the
    # instruction lengths in BLACS, and a finite delay in the PulseBlaster
    #
    # IF YOU CHANGE ONE, YOU MUST CHANGE THE OTHER!
    trigger_delay = 250e-9 
    wait_delay = 100e-9
    trigger_edge_type = 'falling'
    
    def __init__(self,name,trigger_device=None,trigger_connection=None,board_number=0,firmware = '', slow_clock_flag=1,fast_clock_flag=0):
        PseudoClock.__init__(self,name,trigger_device,trigger_connection)
        self.BLACS_connection = board_number
        # TODO: Implement capability checks based on firmware revision of PulseBlaster
        self.firmware_version = firmware
        
        # slow clock flag must be either the integer 0-11 to indicate a flag, or None to indicate not in use.
        if type(slow_clock_flag) == int:
            slow_clock_flag = [slow_clock_flag]
        if slow_clock_flag is not None:
            for flag in slow_clock_flag:
                if not self.flag_valid(flag):
                    raise LabscriptError('The slow clock flag(s) for Pulseblaster %s must either be an integer between 0-%d to indicate slow clock output'%(name, self.n_flags-1) +
                                         ' on that flag or None to indicate the suppression of the slow clock')
        self.slow_clock_flag = slow_clock_flag
            
            
        # if -1 < slow_clock_flag < self.n_flags or slow_clock_flag == None:
            # self.slow_clock_flag = slow_clock_flag
        # else:
            # raise LabscriptError('The slow clock flag for Pulseblaster %s must either be an integer between 0-11 to indicate slow clock output'%name +
                                 # ' on that flag or None to indicate the suppression of the slow clock')
        
        # fast clock flag must be either the integer 0-11 to indicate a flag, or None to indicate not in use.
        if type(fast_clock_flag) == int:
            fast_clock_flag = [fast_clock_flag]
            
        self.extra_clocks = []
        if fast_clock_flag is not None:
            for flag in fast_clock_flag:
                if not self.flag_valid(flag) or (type(self.slow_clock_flag) == list and flag in self.slow_clock_flag):
                    raise LabscriptError('The fast clock flag for Pulseblaster %s must either be an integer between 0-%d to indicate fast clock output'%(name, self.n_flags-1) +
                                         ' on that flag orNone to indicate the suppression of the fast clock')
                self.extra_clocks.append('flag %d'%flag)
        self.fast_clock_flag = fast_clock_flag
            
        
        # if -1 < fast_clock_flag < self.n_flags or fast_clock_flag == None:
            # # the fast clock flag should not be the same as the slow clock flag
            # if fast_clock_flag == slow_clock_flag and fast_clock_flag != None:
                # raise LabscriptError('The fast clock flag for Pulseblaster %s must not be the same as the slow clock flag')
            # else:
                # self.fast_clock_flag = fast_clock_flag
        # else:
            # raise LabscriptError('The fast clock flag for Pulseblaster %s must either be an integer between 0-11 to indicate fast clock output'%name +
                                 # ' on that flag orNone to indicate the suppression of the fast clock')
        
        # Only allow directly connected devices if we don't have a fast clock or a slow clock
        if slow_clock_flag == None and fast_clock_flag == None:
            self.allowed_children = [DDS,DigitalOut]
            self.description = 'PB-DDSII-300 [standalone]' #make the error messages make a little more sense
            self.has_clocks = False
        else:
            self.has_clocks = True
    
    def add_device(self, device):
        Device.add_device(self, device)
        if isinstance(device, DDS):
            # Check that the user has not specified another digital line as the gate for this DDS, that doesn't make sense.
            # Then instantiate a DigitalQuantity to keep track of gating.
            if device.gate is None:
                device.gate = DigitalQuantity(device.name + '_gate', device, 'gate')
            else:
                raise LabscriptError('You cannot specify a digital gate ' +
                                     'for a DDS connected to %s. '% (self.name) + 
                                     'The digital gate is always internal to the Pulseblaster.')
                
    def flag_valid(self, flag):
        if -1 < flag < self.n_flags:
            return True
        return False
        
    def flag_is_clock(self, flag):
        if type(self.slow_clock_flag) == list and flag in self.slow_clock_flag:
            return True
        elif type(self.fast_clock_flag) == list and flag in self.fast_clock_flag:
            return True
        else:
            return False        
    
    def get_direct_outputs(self):
        """Finds out which outputs are directly attached to the PulseBlaster"""
        dig_outputs = []
        dds_outputs = []
        for output in self.get_all_outputs():
            # If the device's parent is a DDS (remembering that DDSs
            # have three fake child devices for amp, freq and phase),
            # then maybe that DDS is one of our direct outputs:
            if isinstance(output.parent_device,DDS) and output.parent_device.parent_device is self:
                # If this is the case, then we're interested in that DDS. But we don't want to count it three times:
                if not output.parent_device in dds_outputs:
                    output = output.parent_device
            if output.parent_device is self:
                try:
                    prefix, connection = output.connection.split()
                    assert prefix == 'flag' or prefix == 'dds'
                    connection = int(connection)
                except:
                    raise LabscriptError('%s %s has invalid connection string: \'%s\'. '%(output.description,output.name,str(output.connection)) + 
                                         'Format must be \'flag n\' with n an integer less than %d, or \'dds n\' with n less than 2.'%self.n_flags)
                if not connection < self.n_flags:
                    raise LabscriptError('%s is set as connected to output connection %d of %s. '%(output.name, connection, self.name) +
                                         'Output connection number must be a integer less than %d.'%self.n_flags)
                if prefix == 'dds' and not connection < 2:
                    raise LabscriptError('%s is set as connected to output connection %d of %s. '%(output.name, connection, self.name) +
                                         'DDS output connection number must be a integer less than 2.')
                if prefix == 'flag' and self.flag_is_clock(connection):
                    raise LabscriptError('%s is set as connected to flag %d of %s.'%(output.name, connection, self.name) +
                                         'This is one of the PulseBlaster\'s clock flags.')
                for other_output in dig_outputs + dds_outputs:
                    if output.connection == other_output.connection:
                        raise LabscriptError('%s and %s are both set as connected to %s of %s.'%(output.name, other_output.name, output.connection, self.name))
                if isinstance(output,DigitalOut):
                	dig_outputs.append(output)
                elif isinstance(output, DDS):
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
        # An array for storing the line numbers of the instructions at
        # which the slow clock ticks:
        slow_clock_indices = []
        # index to keep track of where in output.raw_output the
        # pulseblaster flags are coming from
        i = 0
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
        
        if self.fast_clock_flag is not None:
            for fast_flag in self.fast_clock_flag:
                flags[fast_flag] = 0
        if self.slow_clock_flag is not None:
            for slow_flag in self.slow_clock_flag:
                flags[slow_flag] = 0
            
        pb_inst.append({'freqs': freqregs, 'amps': ampregs, 'phases': phaseregs, 'enables':dds_enables,
                        'flags': ''.join([str(flag) for flag in flags]), 'instruction': 'STOP',
                        'data': 0, 'delay': 10.0/self.clock_limit*1e9})
        pb_inst.append({'freqs': freqregs, 'amps': ampregs, 'phases': phaseregs, 'enables':dds_enables,
                        'flags': ''.join([str(flag) for flag in flags]), 'instruction': 'STOP',
                        'data': 0, 'delay': 10.0/self.clock_limit*1e9})    
        j += 2
        flagstring = '0'*self.n_flags # So that this variable is still defined if the for loop has no iterations
        for k, instruction in enumerate(self.clock):
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
            for output in dig_outputs:
                flagindex = int(output.connection.split()[1])
                flags[flagindex] = int(output.raw_output[i])
            for output in dds_outputs:
                ddsnumber = int(output.connection.split()[1])
                freqregs[ddsnumber] = freqs[ddsnumber][output.frequency.raw_output[i]]
                ampregs[ddsnumber] = amps[ddsnumber][output.amplitude.raw_output[i]]
                phaseregs[ddsnumber] = phases[ddsnumber][output.phase.raw_output[i]]
                dds_enables[ddsnumber] = output.gate.raw_output[i]
            if self.fast_clock_flag is not None:
                for fast_flag in self.fast_clock_flag:
                    if (type(instruction['fast_clock']) == list and 'flag %d'%fast_flag in instruction['fast_clock']) or instruction['fast_clock'] == 'all':
                        flags[fast_flag] = 1
                    else:
                        flags[fast_flag] = 1 if instruction['slow_clock_tick'] else 0
            if self.slow_clock_flag is not None:
                for slow_flag in self.slow_clock_flag:
                    flags[slow_flag] = 1 if instruction['slow_clock_tick'] else 0
            if instruction['slow_clock_tick']:
                slow_clock_indices.append(j)
            flagstring = ''.join([str(flag) for flag in flags])
            if instruction['reps'] > 1048576:
                raise LabscriptError('Pulseblaster cannot support more than 1048576 loop iterations. ' +
                                      str(instruction['reps']) +' were requested at t = ' + str(instruction['start']) + '. '+
                                     'This can be fixed easily enough by using nested loops. If it is needed, ' +
                                     'please file a feature request at' +
                                     'http://redmine.physics.monash.edu.au/projects/labscript.')
                
            # Instruction delays > 55 secs will require a LONG_DELAY
            # to be inserted. How many times does the delay of the
            # loop/endloop instructions go into 55 secs?
            if self.has_clocks:
                quotient, remainder = divmod(instruction['step']/2.0,55.0)
            else:
                quotient, remainder = divmod(instruction['step'],55.0)
            if quotient and remainder < 100e-9:
                # The remainder will be used for the total duration of the LOOP and END_LOOP instructions. 
                # It must not be too short for this, if it is, take one LONG_DELAY iteration and give 
                # its duration to the loop instructions:
                quotient, remainder = quotient - 1, remainder + 55.0
            if self.has_clocks:
                # The loop and endloop instructions will only use the remainder:
                pb_inst.append({'freqs': freqregs, 'amps': ampregs, 'phases': phaseregs, 'enables':dds_enables,
                                'flags': flagstring, 'instruction': 'LOOP',
                                'data': instruction['reps'], 'delay': remainder*1e9})
                if self.fast_clock_flag is not None:
                    for fast_flag in self.fast_clock_flag:
                        flags[fast_flag] = 0
                if self.slow_clock_flag is not None:
                    for slow_flag in self.slow_clock_flag:
                        flags[slow_flag] = 0
                flagstring = ''.join([str(flag) for flag in flags])
            
                # If there was a nonzero quotient, let's wait twice that
                # many multiples of 55 seconds (one multiple of 55 seconds
                # for each of the other two loop and endloop instructions):
                if quotient:
                    pb_inst.append({'freqs': freqregs, 'amps': ampregs, 'phases': phaseregs, 'enables':dds_enables,
                                'flags': flagstring, 'instruction': 'LONG_DELAY',
                                'data': int(2*quotient), 'delay': 55*1e9})
                                
                pb_inst.append({'freqs': freqregs, 'amps': ampregs, 'phases': phaseregs, 'enables':dds_enables,
                                'flags': flagstring, 'instruction': 'END_LOOP',
                                'data': j, 'delay': remainder*1e9})
                                
                # Two instructions were used in the case of there being no LONG_DELAY, 
                # otherwise three. This increment is done here so that the j referred
                # to in the previous line still refers to the LOOP instruction.
                j += 3 if quotient else 2
            else:
                # The loop and endloop instructions will only use the remainder:
                pb_inst.append({'freqs': freqregs, 'amps': ampregs, 'phases': phaseregs, 'enables':dds_enables,
                                'flags': flagstring, 'instruction': 'CONTINUE',
                                'data': 0, 'delay': remainder*1e9})
                # If there was a nonzero quotient, let's wait that many multiples of 55 seconds:
                if quotient:
                    pb_inst.append({'freqs': freqregs, 'amps': ampregs, 'phases': phaseregs, 'enables':dds_enables,
                                'flags': flagstring, 'instruction': 'LONG_DELAY',
                                'data': int(quotient), 'delay': 55*1e9})
                j += 2 if quotient else 1
                
            try:
                if self.clock[k+1] == 'WAIT' or self.clock[k+1]['slow_clock_tick']:
                    i += 1
            except IndexError:
                pass
        # This is how we stop the pulse program. We branch from the last
        # instruction to the zeroth, which BLACS has programmed in with
        # the same values and a WAIT instruction. The PulseBlaster then
        # waits on instuction zero, which is a state ready for either
        # further static updates or buffered mode.
        pb_inst.append({'freqs': freqregs, 'amps': ampregs, 'phases': phaseregs, 'enables':dds_enables,
                        'flags': flagstring, 'instruction': 'BRANCH',
                        'data': 0, 'delay': 10.0/self.clock_limit*1e9})  
                        
        return pb_inst, slow_clock_indices
        
    def write_pb_inst_to_h5(self, pb_inst, slow_clock_indices, hdf5_file):
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
            pb_inst_table[i] = (freq0,phase0,amp0,en0,0,freq1,phase1,amp1,en1,0, flagint, 
                                instructionint, dataint, delaydouble)
        slow_clock_indices = np.array(slow_clock_indices, dtype = np.uint32)                  
        # Okey now write it to the file: 
        group = hdf5_file['/devices/'+self.name]  
        group.create_dataset('PULSE_PROGRAM', compression=config.compression,data = pb_inst_table)   
        for clock_type, time_array in self.times.items():
            group.create_dataset(clock_type, compression=config.compression,data = time_array)         
        group.create_dataset('SLOW_CLOCK', compression=config.compression,data = self.change_times)   
        group.create_dataset('CLOCK_INDICES', compression=config.compression,data = slow_clock_indices)  
        group.attrs['stop_time'] = self.stop_time       
    
    def generate_code(self, hdf5_file):
        # Generate the hardware instructions
        hdf5_file.create_group('/devices/'+self.name)
        PseudoClock.generate_code(self, hdf5_file)
        dig_outputs, dds_outputs = self.get_direct_outputs()
        freqs, amps, phases = self.generate_registers(hdf5_file, dds_outputs)
        pb_inst, slow_clock_indices = self.convert_to_pb_inst(dig_outputs, dds_outputs, freqs, amps, phases)
        self.write_pb_inst_to_h5(pb_inst, slow_clock_indices, hdf5_file)
        
        
            
@RunviewerParser
class MyRunviewerClass(object):
    num_dds = 2
    num_flags = 12
    
    def __init__(self, path, name):
        self.path = path
        self.name = name
        
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
        
            
        
    def get_traces(self,parent=None):
        if parent is None:
            # we're the master pseudoclock, software triggered. So we don't have to worry about trigger delays, etc
            pass
            
        # get the pulse program
        with h5py.File(self.path, 'r') as f:
            pulse_program = f['devices/%s/PULSE_PROGRAM'%self.name][:]
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
        t = 0. # TODO: Offset by initial trigger of parent
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
                    # print 'Wait at %.9f'%t
                    pass
                clock.append(t)
                self._add_pulse_program_row_to_traces(traces,row,dds)
                t+= row['length']*1.0e-9
            
                if row['inst'] == 8: #WAIT
                    #TODO: Offset next time by trigger delay is not master pseudoclock
                    pass
            
            i += 1            
                
        # print 'Stop time: %.9f'%t 
        # now put together the traces
        to_return = {}
        clock = np.array(clock, dtype=np.float64)
        for name, data in traces.items():
            to_return[name] = (clock, np.array(data))
            
        return to_return
    
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
            
            
