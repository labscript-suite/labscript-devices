#####################################################################
#                                                                   #
# /labscript_devices/PrawnDO/labscript_devices.py                   #
#                                                                   #
# Copyright 2023, Philip Starkey, Carter Turnbaugh, Patrick Miller  #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from labscript import (
    IntermediateDevice,
    PseudoclockDevice,
    Pseudoclock,
    ClockLine,
    DigitalOut,
    Trigger,
    bitfield,
    set_passed_properties,
    LabscriptError
)
import numpy as np

class _PrawnDOPseudoclock(Pseudoclock):
    """Dummy pseudoclock for use with PrawnDO.
    
    This pseudoclock ensures only one clockline is attached.
    """

    def add_device(self, device):

        if not isinstance(device, _PrawnDOClockline) or self.child_devices:
            # only allow one child dummy clockline
            raise LabscriptError("You are trying to access the special, dummy, Pseudoclock of the PrawnDO "
                                    f"{self.parent_device.name}. This is for internal use only.")
        else:
            Pseudoclock.add_device(self, device)


class _PrawnDOClockline(ClockLine):
    """Dummy clockline for use with PrawnDO
    
    Ensures only a single _PrawnDODirectOutputs is connected to the PrawnDO
    """

    def add_device(self, device):

        if not isinstance(device, _PrawnDigitalOutputs) or self.child_devices:
            # only allow one child device
            raise LabscriptError("You are trying to access the special, dummy, Clockline of the PrawnDO "
                                    f"{self.pseudoclock_device.name}. This is for internal use only.")
        else:
            ClockLine.add_device(self, device)


class _PrawnDigitalOutputs(IntermediateDevice):
    allowed_children = [DigitalOut]

    allowed_channels = tuple(range(16))

    def __init__(self, name, parent_device,
                 **kwargs):
        """Collective output class for the PrawnDO.
        
        This class aggregates the 16 individual digital outputs of the PrawnDO.
        It is for internal use of the PrawnDO only.

        Args:
            name (str): name to assign
            parent_device (Device): Parent device PrawnDO is connected to
        """

        IntermediateDevice.__init__(self, name, parent_device, **kwargs)
        self.connected_channels = []

    def add_device(self, device):
        """Confirms channel specified is valid before adding
        
        Args:
            device (): Device to attach. Must be a digital output.
                Allowed connections are a string of the form `doXX`
        """

        conn = device.connection
        chan = int(conn.split('do')[-1])

        if chan not in self.allowed_channels:
            raise LabscriptError(f'Invalid channel specification: {conn}')
        if chan in self.connected_channels:
            raise LabscriptError(f'Channel {conn} already connected to {self.parent_device.name}')
        
        self.connected_channels.append(chan)
        super().add_device(device)
    

class PrawnDO(PseudoclockDevice):
    description = "PrawnDO device"

    # default specs assuming 100MHz system clock
    clock_limit = 1 / 100e-9
    "Maximum allowable clock rate"
    clock_resolution = 10e-9
    "Minimum resolvable unit of time, corresponsd to system clock period."
    minimum_duration = 50e-9
    "Minimum time between updates on the outputs."
    wait_delay = 50e-9
    "Minimum required length of wait before a retrigger can be detected."
    input_response_time = 50e-9
    "Time between hardware trigger and output starting."
    trigger_delay = 50e-9 # TODO: gets applied twice on waits...
    trigger_minimum_duration = 160e-9
    "Minimum required duration of hardware trigger. A fairly large over-estimate."

    allowed_children = [_PrawnDOPseudoclock]

    max_instructions = 30000
    """Maximum number of instructions. Set by zmq timeout when sending the commands."""

    @set_passed_properties(
        property_names={
            'connection_table_properties': [
                'com_port',
            ],
            'device_properties': [
                'clock_frequency',
                'external_clock',
                'clock_limit',
                'clock_resolution',
                'minimum_duration',
                'input_response_time',
                'trigger_delay',
                'trigger_minimum_duration',
                'wait_delay',
            ]
        }
    )
    def __init__(self, name, 
                 trigger_device = None,
                 trigger_connection = None,
                 clock_line = None,
                 com_port = 'COM1',
                 clock_frequency = 100e6,
                 external_clock = False,
                ):
        """PrawnDO digital output device.
        
        This labscript device provides general purpose digital outputs
        using a Raspberry Pi Pico with custom firmware.

        It supports two types of connections to a parent device:
        direct to a :class:`~.Clockline` via the `clock_line` argument or
        through a :class:`~.Trigger` from an :class:`~.IntermediateDevice`
        via the `trigger_device` and `trigger_connection` arguments.
        Only one should be supplied.


        Args:
            name (str): python variable name to assign to the PrawnDO
            trigger_device (:class:`~.IntermediateDevice`, optional):
                Device that will send the starting hardware trigger.
                Used when connecting to an `IntermediateDevice` via a `DigitalOut`.
            trigger_connection (str, optional): Which output of the `trigger_device`
                is connected to the PrawnDO hardware trigger input.
                Not required when directly connected to a `Clockline`.
            clock_line (:class:`~.Clockline`, optional):
                Used when connected directly to a `Clockline`.
                Not required if using a trigger device.
            com_port (str): COM port assinged to the PrawnDO by the OS.
                Takes the form of `COMd` where `d` is an integer.
            clock_frequency (float, optional): System clock frequency, in Hz.
                Must be less than 133 MHz. Default is `100e6`.
            external_clock (bool, optional): Whether to use an external clock.
                Default is `False`.
        """

        if clock_frequency > 133e6:
            raise ValueError('Clock frequency must be less than 133 MHz')
        
        self.external_clock = external_clock
        self.clock_frequency = clock_frequency
        # update specs based on clock frequency
        if self.clock_frequency != 100e6:
            # factor to scale times by
            factor = 100e6/self.clock_frequency
            self.clock_limit *= factor
            self.clock_resolution *= factor
            self.minimum_duration *= factor
            self.wait_delay *= factor
            self.input_response_time *= factor
            self.trigger_delay *= factor
            self.trigger_minimum_duration *= factor

        if clock_line is not None and trigger_device is not None:
            raise LabscriptError("Provide only a trigger_device or a clock_line, not both")
        if clock_line is not None:
            # make internal Intermediate device and trigger to connect it
            self.__intermediate = _PrawnDOIntermediateDevice(f'{name:s}__intermediate',
                                                             clock_line)
            PseudoclockDevice.__init__(self, name, self.__intermediate, 'internal')
        else:
            # normal pseudoclock device triggering
            PseudoclockDevice.__init__(self, name, trigger_device, trigger_connection)

        # set up internal connections to allow digital outputs
        self.__pseudoclock = _PrawnDOPseudoclock(f'{name:s}__pseudoclock', self, '_')
        self.__clockline = _PrawnDOClockline(f'{name:s}__clockline',
                                             self.__pseudoclock, '_')
        self.outputs = _PrawnDigitalOutputs(f'{name:s}__pod', self.__clockline)

        self.BLACS_connection = com_port

        self._initial_trigger_time = 0

    # following three defs ensure initial_trigger_time is not modified
    # when directly triggered from a clockline using an internal IntermediateDevice
    @property
    def initial_trigger_time(self):
        return self._initial_trigger_time
    
    @initial_trigger_time.setter
    def initial_trigger_time(self, value):
        if value != 0 and hasattr(self, "__intermediate"):
            raise LabscriptError("You cannot set the initial trigger time when the PrawnDO is directly triggered by a clockline")
        self._initial_trigger_time = value

    def set_initial_trigger_time(self, *args, **kwargs):
        if hasattr(self, "__intermediate"):
            raise LabscriptError("You cannot set the initial trigger time when the PrawnDO is directly triggered by a clockline")
        return super().set_initial_trigger_time(*args, **kwargs)

    def add_device(self, device):

        if isinstance(device, _PrawnDOPseudoclock):
            super().add_device(device)
        elif isinstance(device, DigitalOut):
            raise LabscriptError(f"Digital outputs must be connected to {self.name:s}.outputs")
        else:
            raise LabscriptError(f"You have connected unsupported {device.name:s} (class {device.__class__}) "
                                 f"to {self.name:s}")


    def generate_code(self, hdf5_file):
        PseudoclockDevice.generate_code(self, hdf5_file)

        bits = [0] * 16 # Start with a list of 16 zeros
        # Isolating the Pod child device in order to access the output change 
        # times to store in the array

        # Retrieving all of the outputs contained within the pods and
        # collecting/consolidating the times when they change
        outputs = self.get_all_outputs()
        times = self.__pseudoclock.times[self.__clockline]
        instructions = self.__pseudoclock.clock
        if len(times) == 0:
            # no instructions, so return
            return

        # get where wait instructions should be added from clock instructions
        wait_idxs = [i for i,instr in enumerate(instructions) if instr=='WAIT']

        # Retrieving the time series of each DigitalOut to be stored
        # as the output word for the pins
        for output in outputs:  
            output.make_timeseries(times)
            chan = int(output.connection.split('do')[-1])
            bits[chan] = np.asarray(output.timeseries, dtype = np.uint16)
        # Merge list of lists into an array with a single 16 bit integer column
        bit_sets = np.array(bitfield(bits, dtype=np.uint16))

        # Now create the reps array (ie times between changes in number of clock cycles)
        reps = np.rint(np.diff(times)/self.clock_resolution).astype(np.uint32)
        
        # add stop command sequence
        # final output already in bit_sets
        reps = np.append(reps, 0) # causes last instruction to hold
        # next two indicate the stop
        bit_sets = np.append(bit_sets, 0) # this value is ignored
        reps = np.append(reps, 0)

        # Add in wait instructions to reps
        # have output maintain previous output state during wait
        reps = np.insert(reps, wait_idxs, 0)
        bit_sets = np.insert(bit_sets, wait_idxs, bit_sets[wait_idxs])

        # Raising an error if the user adds too many commands
        if reps.size > self.max_instructions:
            raise LabscriptError (
                "Too Many Commands"
            )

        group = hdf5_file['devices'].require_group(self.name)
        # combining reps and bit sets into single structured array for saving to hdf5 file
        dtype = np.dtype([('bit_sets', '<u2'),
                          ('reps', '<u4')])
        pulse_program = np.zeros(len(reps), dtype=dtype)
        pulse_program['bit_sets'] = bit_sets
        pulse_program['reps'] = reps
        group.create_dataset('pulse_program', data=pulse_program)


class _PrawnDOIntermediateDevice(IntermediateDevice):
    description = "PrawnDO Internal Intermediate Device"

    allowed_children = [Trigger]
        