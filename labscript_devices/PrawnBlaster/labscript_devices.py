#####################################################################
#                                                                   #
# /labscript_devices/PrawnBlaster/labscript_devices.py              #
#                                                                   #
# Copyright 2021, Philip Starkey                                    #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

import copy

from labscript import (
    ClockLine,
    IntermediateDevice,
    LabscriptError,
    PseudoclockDevice,
    Pseudoclock,
    WaitMonitor,
    compiler,
    config,
    set_passed_properties,
)
import numpy as np


class _PrawnBlasterPseudoclock(Pseudoclock):
    """Customized Clockline for use with the PrawnBlaster.

    This Pseudoclock retains information about which hardware clock
    it is associated with, and ensures only one clockline per
    pseudoclock.
    """
    def __init__(self, i, *args, **kwargs):
        """
        Args:
            i (int): Specifies which hardware pseudoclock this device
                is associated with.
        """
        super().__init__(*args, **kwargs)
        self.i = i

    def add_device(self, device):
        """
        Args:
            device (:class:`~labscript.ClockLine`): Clockline to attach to the
                pseudoclock.
        """
        if isinstance(device, ClockLine):
            # only allow one child
            if self.child_devices:
                raise LabscriptError(
                    f"Each pseudoclock of the PrawnBlaster {self.parent_device.name} only supports 1 clockline, which is automatically created. Please use the clockline located at {self.parent_device.name}.clocklines[{self.i}]"
                )
            Pseudoclock.add_device(self, device)
        else:
            raise LabscriptError(
                f"You have connected {device.name} to {self.name} (a Pseudoclock of {self.parent_device.name}), but {self.name} only supports children that are ClockLines. Please connect your device to {self.parent_device.name}.clocklines[{self.i}] instead."
            )


#
# Define dummy pseudoclock/clockline/intermediatedevice to trick wait monitor
# since everything is handled internally in this device
#
class _PrawnBlasterDummyPseudoclock(Pseudoclock):
    """Dummy Pseudoclock labscript device used internally to allow 
    :class:`~labscript.WaitMonitor` to work internally to the PrawnBlaster."""
    def add_device(self, device):
        if isinstance(device, _PrawnBlasterDummyClockLine):
            if self.child_devices:
                raise LabscriptError(
                    f"You are trying to access the special, dummy, PseudoClock of the PrawnBlaster {self.pseudoclock_device.name}. This is for internal use only."
                )
            Pseudoclock.add_device(self, device)
        else:
            raise LabscriptError(
                f"You are trying to access the special, dummy, PseudoClock of the PrawnBlaster {self.pseudoclock_device.name}. This is for internal use only."
            )

    # do nothing, this is a dummy class!
    def generate_code(self, *args, **kwargs):
        pass


class _PrawnBlasterDummyClockLine(ClockLine):
    """Dummy Clockline labscript device used internally to allow 
    :class:`~labscript.WaitMonitor` to work internally to the PrawnBlaster."""
    def add_device(self, device):
        if isinstance(device, _PrawnBlasterDummyIntermediateDevice):
            if self.child_devices:
                raise LabscriptError(
                    f"You are trying to access the special, dummy, ClockLine of the PrawnBlaster {self.pseudoclock_device.name}. This is for internal use only."
                )
            ClockLine.add_device(self, device)
        else:
            raise LabscriptError(
                f"You are trying to access the special, dummy, ClockLine of the PrawnBlaster {self.pseudoclock_device.name}. This is for internal use only."
            )

    # do nothing, this is a dummy class!
    def generate_code(self, *args, **kwargs):
        pass


class _PrawnBlasterDummyIntermediateDevice(IntermediateDevice):
    """Dummy intermediate labscript device used internally to attach 
    :class:`~labscript.WaitMonitor` objects to the PrawnBlaster."""

    def add_device(self, device):
        if isinstance(device, WaitMonitor):
            IntermediateDevice.add_device(self, device)
        else:
            raise LabscriptError(
                "You can only connect an instance of WaitMonitor to the device %s.internal_wait_monitor_outputs"
                % (self.pseudoclock_device.name)
            )

    # do nothing, this is a dummy class!
    def generate_code(self, *args, **kwargs):
        pass


class PrawnBlaster(PseudoclockDevice):
    description = "PrawnBlaster"
    clock_limit = 1 / 100e-9
    """Maximum allowable clock rate."""
    clock_resolution = 20e-9
    """Minimum resolvable time for a clock tick."""
    input_response_time = 50e-9
    """Time necessary for hardware to respond to a hardware trigger. 
    Empirically determined to be a ~50 ns buffer on the input.
    """
    trigger_delay = input_response_time + 80e-9
    """Processing time delay after trigger is detected. Due to firmware, there is an
    80 ns delay between trigger detection and first output pulse."""
    trigger_minimum_duration = 160e-9
    """Minimum required width of hardware trigger. An overestimate that covers
    currently unsupported indefinite waits."""
    wait_delay = 40e-9
    """Minimum required length of a wait before retrigger can be detected.
    Corresponds to 4 instructions."""
    allowed_children = [_PrawnBlasterPseudoclock, _PrawnBlasterDummyPseudoclock]
    max_instructions = 30000
    """Maximum numaber of instructions per pseudoclock. Max is 30,000 for a single
    pseudoclock."""

    @set_passed_properties(
        property_names={
            "connection_table_properties": [
                "com_port",
                "in_pins",
                "out_pins",
                "num_pseudoclocks",
            ],
            "device_properties": [
                "clock_frequency",
                "external_clock_pin",
                "clock_limit",
                "clock_resolution",
                "input_response_time",
                "trigger_delay",
                "trigger_minimum_duration",
                "wait_delay",
                "max_instructions",
            ],
        }
    )
    def __init__(
        self,
        name,
        trigger_device=None,
        trigger_connection=None,
        com_port="COM1",
        num_pseudoclocks=1,
        out_pins=None,
        in_pins=None,
        clock_frequency=100e6,
        external_clock_pin=None,
        use_wait_monitor=True,
    ):
        """PrawnBlaster Pseudoclock labscript device.

        This labscript device creates Pseudoclocks based on the PrawnBlaster,
        a Raspberry Pi Pico with custom firmware.

        Args:
            name (str): python variable name to assign to the PrawnBlaster
            com_port (str): COM port assigned to the PrawnBlaster by the OS. Takes 
                the form of `'COMd'`, where `d` is an integer.
            num_pseudoclocks (int): Number of pseudoclocks to create. Ranges from 1-4.
            trigger_device (:class:`~labscript.IntermediateDevice`, optional): Device
                that will send the hardware start trigger when using the PrawnBlaster
                as a secondary Pseudoclock.
            trigger_connection (str, optional): Which output of the `trigger_device`
                is connected to the PrawnBlaster hardware trigger input.
            out_pins (list, optional): What outpins to use for the pseudoclock outputs.
                Must have length of at least `num_pseudoclocks`. Defaults to `[9,11,13,15]`
            in_pins (list, optional): What inpins to use for the pseudoclock hardware
                triggering. Must have length of at least `num_pseudoclocks`. 
                Defaults to `[0,0,0,0]`
            clock_frequency (float, optional): Frequency of clock. Standard range
                accepts up to 133 MHz. An experimental overclocked firmware is 
                available that allows higher frequencies.
            external_clock_pin (int, optional): If not `None` (the default), 
                the PrawnBlaster uses an external clock on the provided pin. Valid
                options are `20` and `22`. The external frequency must be defined
                using `clock_frequency`.
            use_wait_monitor (bool, optional): Configure the PrawnBlaster to
                perform its own wait monitoring.

        """

        # Check number of pseudoclocks is within range
        if num_pseudoclocks < 1 or num_pseudoclocks > 4:
            raise LabscriptError(
                f"The PrawnBlaster {name} only supports between 1 and 4 pseudoclocks"
            )

        # Update the specs based on the number of pseudoclocks
        self.max_instructions = self.max_instructions // num_pseudoclocks
        # Update the specs based on the clock frequency
        if self.clock_resolution != 2 / clock_frequency:
            factor = (2 / clock_frequency) / self.clock_resolution
            self.clock_limit *= factor
            self.clock_resolution *= factor
            self.input_response_time *= factor
            self.trigger_delay *= factor
            self.trigger_minimum_duration *= factor
            self.wait_delay *= factor

        # Instantiate the base class
        PseudoclockDevice.__init__(self, name, trigger_device, trigger_connection)
        self.num_pseudoclocks = num_pseudoclocks
        # Wait monitor can only be used if this is the master pseudoclock
        self.use_wait_monitor = use_wait_monitor and self.is_master_pseudoclock

        # Set the BLACS connections
        self.BLACS_connection = com_port

        # Check in/out pins
        if out_pins is None:
            out_pins = [9, 11, 13, 15]
        if in_pins is None:
            in_pins = [0, 0, 0, 0]
        if len(out_pins) < num_pseudoclocks:
            raise LabscriptError(
                f"The PrawnBlaster {self.name} is configured with {num_pseudoclocks} but only has pin numbers specified for {len(out_pins)}."
            )
        else:
            self.out_pins = out_pins[:num_pseudoclocks]
        if len(in_pins) < num_pseudoclocks:
            raise LabscriptError(
                f"The PrawnBlaster {self.name} is configured with {num_pseudoclocks} but only has pin numbers specified for {len(in_pins)}."
            )
        else:
            self.in_pins = in_pins[:num_pseudoclocks]

        self._pseudoclocks = []
        self._clocklines = []
        for i in range(num_pseudoclocks):
            self._pseudoclocks.append(
                _PrawnBlasterPseudoclock(
                    i,
                    name=f"{name}_pseudoclock_{i}",
                    pseudoclock_device=self,
                    connection=f"pseudoclock {i}",
                )
            )
            self._clocklines.append(
                ClockLine(
                    name=f"{name}_clock_line_{i}",
                    pseudoclock=self._pseudoclocks[i],
                    connection=f"GPIO {self.out_pins[i]}",
                )
            )

        if self.use_wait_monitor:
            # Create internal devices for connecting to a wait monitor
            self.__wait_monitor_dummy_pseudoclock = _PrawnBlasterDummyPseudoclock(
                "%s__dummy_wait_pseudoclock" % name, self, "_"
            )
            self.__wait_monitor_dummy_clock_line = _PrawnBlasterDummyClockLine(
                "%s__dummy_wait_clock_line" % name,
                self.__wait_monitor_dummy_pseudoclock,
                "_",
            )
            self.__wait_monitor_intermediate_device = (
                _PrawnBlasterDummyIntermediateDevice(
                    "%s_internal_wait_monitor_outputs" % name,
                    self.__wait_monitor_dummy_clock_line,
                )
            )

            # Create the wait monitor
            WaitMonitor(
                "%s__wait_monitor" % name,
                self.internal_wait_monitor_outputs,
                "internal",
                self.internal_wait_monitor_outputs,
                "internal",
                self.internal_wait_monitor_outputs,
                "internal",
            )

    @property
    def internal_wait_monitor_outputs(self):
        return self.__wait_monitor_intermediate_device

    @property
    def pseudoclocks(self):
        """Returns a list of the automatically generated
        :class:`_PrawnBlasterPseudoclock` objects."""

        return copy.copy(self._pseudoclocks)

    @property
    def clocklines(self):
        """Returns a list of the automatically generated 
        :class:`~labscript.ClockLine` objects."""

        return copy.copy(self._clocklines)

    def add_device(self, device):
        """Adds child devices.

        This is automatically called by the labscript compiler.

        Args:
            device (:class:`_PrawnBlasterPseudoclock` or :class:`_PrawnBlasterDummyPseudoclock`):
                Instance to attach to the device. Only the allowed children can be attached.
        """

        if len(self.child_devices) < (
            self.num_pseudoclocks + self.use_wait_monitor
        ) and isinstance(
            device, (_PrawnBlasterPseudoclock, _PrawnBlasterDummyPseudoclock)
        ):
            PseudoclockDevice.add_device(self, device)
        elif isinstance(device, _PrawnBlasterPseudoclock):
            raise LabscriptError(
                f"The {self.description} {self.name} automatically creates the correct number of pseudoclocks."
                + "Instead of instantiating your own Pseudoclock object, please use the internal"
                + f" ones stored in {self.name}.pseudoclocks"
            )
        else:
            raise LabscriptError(
                f"You have connected {device.name} (class {device.__class__}) to {self.name}, but {self.name} does not support children with that class."
            )

    def generate_code(self, hdf5_file):
        """Generates the hardware instructions for the pseudoclocks.

        This is automatically called by the labscript compiler.

        Args:
            hdf5_file (:class:`h5py.File`): h5py file object for shot 
        """

        PseudoclockDevice.generate_code(self, hdf5_file)
        group = self.init_device_group(hdf5_file)

        current_wait_index = 0
        wait_table = sorted(compiler.wait_table)

        # For each pseudoclock
        for i, pseudoclock in enumerate(self.pseudoclocks):
            current_wait_index = 0

            # Compress clock instructions with the same half_period
            reduced_instructions = []
            for instruction in pseudoclock.clock:
                if instruction == "WAIT":
                    # If we're using the internal wait monitor, set the timeout
                    if self.use_wait_monitor:
                        # Get the wait timeout value
                        wait_timeout = compiler.wait_table[
                            wait_table[current_wait_index]
                        ][1]
                        current_wait_index += 1
                        # The following half_period and reps indicates a wait instruction
                        reduced_instructions.append(
                            {
                                "half_period": round(
                                    wait_timeout / (self.clock_resolution / 2)
                                ),
                                "reps": 0,
                            }
                        )
                        continue
                    # Else, set an indefinite wait and wait for a trigger from something else.
                    else:
                        # Two waits in a row are an indefinite wait
                        reduced_instructions.append(
                            {
                                "half_period": 2 ** 32 - 1,
                                "reps": 0,
                            }
                        )
                        reduced_instructions.append(
                            {
                                "half_period": 2 ** 32 - 1,
                                "reps": 0,
                            }
                        )

                # Normal instruction
                reps = instruction["reps"]
                # half_period is in quantised units:
                half_period = int(round(instruction["step"] / self.clock_resolution))
                if (
                    # If there is a previous instruction
                    reduced_instructions
                    # And it's not a wait
                    and reduced_instructions[-1]["reps"] != 0
                    # And the half_periods match
                    and reduced_instructions[-1]["half_period"] == half_period
                    # And the sum of the previous reps and current reps won't push it over the limit
                    and (reduced_instructions[-1]["reps"] + reps) < (2 ** 32 - 1)
                ):
                    # Combine instructions!
                    reduced_instructions[-1]["reps"] += reps
                else:
                    # New instruction
                    reduced_instructions.append(
                        {"half_period": half_period, "reps": reps}
                    )

            # Only add this if there is room in the instruction table. The PrawnBlaster
            # firmware has extre room at the end for an instruction that is always 0
            # and cannot be set over serial!
            if len(reduced_instructions) != self.max_instructions:
                # The following half_period and reps indicates a stop instruction:
                reduced_instructions.append({"half_period": 0, "reps": 0})

            # Check we have not exceeded the maximum number of supported instructions
            # for this number of speudoclocks
            if len(reduced_instructions) > self.max_instructions:
                raise LabscriptError(
                    f"{self.description} {self.name}.clocklines[{i}] has too many instructions. It has {len(reduced_instructions)} and can only support {self.max_instructions}"
                )

            # Store these instructions to the h5 file:
            dtypes = [("half_period", int), ("reps", int)]
            pulse_program = np.zeros(len(reduced_instructions), dtype=dtypes)
            for j, instruction in enumerate(reduced_instructions):
                pulse_program[j]["half_period"] = instruction["half_period"]
                pulse_program[j]["reps"] = instruction["reps"]
            group.create_dataset(
                f"PULSE_PROGRAM_{i}", compression=config.compression, data=pulse_program
            )

        # This is needed so the BLACS worker knows whether or not to be a wait monitor
        self.set_property(
            "is_master_pseudoclock",
            self.is_master_pseudoclock,
            location="device_properties",
        )
        self.set_property("stop_time", self.stop_time, location="device_properties")
