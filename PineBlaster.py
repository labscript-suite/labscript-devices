#####################################################################
#                                                                   #
# /PineBlaster.py                                                   #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################

from labscript import PseudoclockDevice, Pseudoclock, ClockLine, config, LabscriptError
from labscript_devices import runviewer_parser

import numpy as np
import labscript_utils.h5_lock, h5py


# Define a PineBlasterPseudoClock that only accepts one child clockline
class PineBlasterPseudoclock(Pseudoclock):    
    def add_device(self, device):
        if isinstance(device, ClockLine):
            # only allow one child
            if self.child_list:
                raise LabscriptError('The pseudoclock of the PineBlaster %s only supports 1 clockline, which is automatically created. Please use the clockline located at %s.clockline'%(self.parent_device.name, self.parent_device.name))
            Pseudoclock.add_device(self, device)
        else:
            raise LabscriptError('You have connected %s to %s (the Pseudoclock of %s), but %s only supports children that are ClockLines. Please connect your device to %s.clockline instead.'%(device.name, self.name, self.parent_device.name, self.name, self.parent_device.name))
 
        
class PineBlaster(PseudoclockDevice):
    description = 'PineBlaster'
    clock_limit = 10e6
    clock_resolution = 25e-9
    clock_type = 'fast clock'
    # Todo: find out what this actually is:
    trigger_delay = 1e-6
    # Todo: find out what this actually is:
    wait_delay = 2.5e-6
    allowed_children = [PineBlasterPseudoclock]
    
    max_instructions = 15000
    
    def __init__(self, name, trigger_device=None, trigger_connection=None, usbport='COM1'):
        PseudoclockDevice.__init__(self, name, trigger_device, trigger_connection)
        self.BLACS_connection = usbport
        
        # create Pseudoclock and clockline
        self._pseudoclock = PineBlasterPseudoclock('%s_pseudoclock'%name, self, 'clock') # possibly a better connection name than 'clock'?
        # Create the internal direct output clock_line
        self._clock_line = ClockLine('%s_clock_line'%name, self.pseudoclock, 'internal')
    
    @property
    def pseudoclock(self):
        return self._pseudoclock
    
    # Note, not to be confused with Device.parent_clock_line which returns the parent ClockLine
    # This one gives the automatically created ClockLine object
    @property
    def clockline(self):
        return self._clock_line
    
    def add_device(self, device):
        if not self.child_list and isinstance(device, Pseudoclock):
            PseudoclockDevice.add_device(self, device)            
        elif isinstance(device, Pseudoclock):
            raise LabscriptError('The %s %s automatically creates a Pseudoclock because it only supports one. '%(self.description, self.name) +
                                 'Instead of instantiating your own Pseudoclock object, please use the internal' +
                                 ' one stored in %s.pseudoclock'%self.name)
        else:
            raise LabscriptError('You have connected %s (class %s) to %s, but %s does not support children with that class.'%(device.name, device.__class__, self.name, self.name))
    
    def generate_code(self, hdf5_file):
        PseudoclockDevice.generate_code(self, hdf5_file)
        group = hdf5_file['devices'].create_group(self.name)   
        
        # compress clock instructions with the same period: This will
        # halve the number of instructions roughly, since the PineBlaster
        # does not have a 'slow clock':
        reduced_instructions = []
        for instruction in self.pseudoclock.clock:
            if instruction == 'WAIT':
                # The following period and reps indicates a wait instruction
                reduced_instructions.append({'period': 0, 'reps': 1})
                continue
            reps = instruction['reps']
            # period is in quantised units:
            period = int(round(instruction['step']/self.clock_resolution))
            if reduced_instructions and reduced_instructions[-1]['period'] == period:
                reduced_instructions[-1]['reps'] += reps
            else:
                reduced_instructions.append({'period': period, 'reps': reps})
        # The following period and reps indicates a stop instruction:
        reduced_instructions.append({'period': 0, 'reps': 0})
        if len(reduced_instructions) > self.max_instructions:
            raise LabscriptError("%s %s has too many instructions. It has %d and can only support %d"%(self.description, self.name, len(reduced_instructions), self.max_instructions))
        # Store these instructions to the h5 file:
        dtypes = [('period',int),('reps',int)]
        pulse_program = np.zeros(len(reduced_instructions),dtype=dtypes)
        for i, instruction in enumerate(reduced_instructions):
            pulse_program[i]['period'] = instruction['period']
            pulse_program[i]['reps'] = instruction['reps']
        group.create_dataset('PULSE_PROGRAM', compression = config.compression, data=pulse_program)
        # TODO: is this needed, the PulseBlasters don't save it... 
        group.attrs['is_master_pseudoclock'] = self.is_master_pseudoclock
 

@runviewer_parser
class RunviewerClass(object):
    clock_resolution = 25e-9
    clock_type = 'fast clock'
    # Todo: find out what this actually is:
    trigger_delay = 1e-6
    # Todo: find out what this actually is:
    wait_delay = 2.5e-6
    
    def __init__(self, path, name):
        self.path = path
        self.name = name
        
            
    def get_traces(self,clock=None):
        if clock is not None:
            times, clock_value = clock[0], clock[1]
            clock_indices = np.where((clock_value[1:]-clock_value[:-1])==1)[0]+1
            # If initial clock value is 1, then this counts as a rising edge (clock should be 0 before experiment)
            # but this is not picked up by the above code. So we insert it!
            if clock_value[0] == 1:
                clock_indices = np.insert(clock_indices, 0, 0)
            clock_ticks = times[clock_indices]

        
            
        # get the pulse program
        with h5py.File(self.path, 'r') as f:
            pulse_program = f['devices/%s/PULSE_PROGRAM'%self.name][:]
            
        time = []
        states = []
        trigger_index = 0
        t = 0 if clock is None else clock_ticks[trigger_index]+self.trigger_delay
        trigger_index += 1
        
        clock_factor = self.clock_resolution/2.
        
        for row in pulse_program:
            if row['period'] == 0:
                #special case
                if row['reps'] == 1: # WAIT
                    if clock is not None:
                        t = clock_ticks[trigger_index]+self.trigger_delay
                        trigger_index += 1
                    else:
                        t += self.wait_delay
            else:    
                for i in range(row['reps']):
                    for j in range(1, -1, -1):
                        time.append(t)
                        states.append(j)
                        t += row['period']*clock_factor
                        
        traces = {'fast clock':(np.array(time), np.array(states))}
        return traces
    
