#####################################################################
#                                                                   #
# /labscript_devices/DummyPseudoclock/DummyPseudoclock.py           #
#                                                                   #
# Copyright 2017, Christopher Billington                            #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

# This file represents a dummy labscript device for purposes of testing BLACS
# and labscript. The device is a PseudoclockDevice, and can be the sole device
# in a connection table or experiment.

from labscript import PseudoclockDevice, Pseudoclock, ClockLine, config, LabscriptError
import numpy as np

class _DummyPseudoclock(Pseudoclock):    
    def add_device(self, device):
        if isinstance(device, ClockLine):
            # only allow one child
            if self.child_devices:
                raise LabscriptError('The pseudoclock of the DummyPseudoclock %s only supports 1 clockline, which is automatically created. Please use the clockline located at %s.clockline'%(self.parent_device.name, self.parent_device.name))
            Pseudoclock.add_device(self, device)
        else:
            raise LabscriptError('You have connected %s to %s (the Pseudoclock of %s), but %s only supports children that are ClockLines. Please connect your device to %s.clockline instead.'%(device.name, self.name, self.parent_device.name, self.name, self.parent_device.name))


class DummyPseudoclock(PseudoclockDevice):

    description = 'Dummy pseudoclock'
    clock_limit = 10e6
    clock_resolution = 25e-9
    trigger_delay = 350e-9
    wait_delay = 2.5e-6
    allowed_children = [_DummyPseudoclock]
    max_instructions = 1e5

    def __init__(
        self, name='dummy_pseudoclock', BLACS_connection='dummy_connection', **kwargs
    ):
        self.BLACS_connection = BLACS_connection
        PseudoclockDevice.__init__(self, name, None, None, **kwargs)
        self._pseudoclock = _DummyPseudoclock(
            name=f'{name}_pseudoclock',
            pseudoclock_device=self,
            connection='pseudoclock',
        )
        self._clock_line = ClockLine(
            name=f'{name}_clock_line',
            pseudoclock=self.pseudoclock,
            connection='internal',
        )

    @property
    def pseudoclock(self):
        return self._pseudoclock

    @property
    def clockline(self):
        return self._clock_line

    def add_device(self, device):
        if not self.child_devices and isinstance(device, Pseudoclock):
            PseudoclockDevice.add_device(self, device)            
        elif isinstance(device, Pseudoclock):
            raise LabscriptError('The %s %s automatically creates a Pseudoclock because it only supports one. '%(self.description, self.name) +
                                 'Instead of instantiating your own Pseudoclock object, please use the internal' +
                                 ' one stored in %s.pseudoclock'%self.name)
        else:
            raise LabscriptError('You have connected %s (class %s) to %s, but %s does not support children with that class.'%(device.name, device.__class__, self.name, self.name))

    def generate_code(self, hdf5_file):
        PseudoclockDevice.generate_code(self, hdf5_file)
        group = self.init_device_group(hdf5_file)

        # Compress clock instructions with the same period
        # This will halve the number of instructions roughly,
        # since the DummyPseudoclock does not have a 'slow clock'
        reduced_instructions = []
        for instruction in self.pseudoclock.clock:
            if instruction == 'WAIT':
                # The following period and reps indicates a wait instruction
                reduced_instructions.append({'period': 0, 'reps': 1})
                continue
            reps = instruction['reps']
            # period is in quantised units:
            period = int(round(instruction['step'] / self.clock_resolution))
            if reduced_instructions and reduced_instructions[-1]['period'] == period:
                reduced_instructions[-1]['reps'] += reps
            else:
                reduced_instructions.append({'period': period, 'reps': reps})
        # The following period and reps indicates a stop instruction:
        reduced_instructions.append({'period': 0, 'reps': 0})
        if len(reduced_instructions) > self.max_instructions:
            raise LabscriptError(
                "%s %s has too many instructions. It has %d and can only support %d"
                % (
                    self.description,
                    self.name,
                    len(reduced_instructions),
                    self.max_instructions,
                )
            )
        # Store these instructions to the h5 file:
        dtypes = [('period', int), ('reps', int)]
        pulse_program = np.zeros(len(reduced_instructions), dtype=dtypes)
        for i, instruction in enumerate(reduced_instructions):
            pulse_program[i]['period'] = instruction['period']
            pulse_program[i]['reps'] = instruction['reps']
        group.create_dataset(
            'PULSE_PROGRAM', compression=config.compression, data=pulse_program
        )
        # TODO: is this needed, the PulseBlasters don't save it...
        self.set_property(
            'is_master_pseudoclock',
            self.is_master_pseudoclock,
            location='device_properties',
        )
        self.set_property('stop_time', self.stop_time, location='device_properties')
