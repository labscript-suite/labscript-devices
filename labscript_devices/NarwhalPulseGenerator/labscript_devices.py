#####################################################################
#                                                                   #
# /labscript_devices/NarwhalPulseGenerator/labscript_devices.py     #
#                                                                   #
# Copyright 2026, Christopher Billington                            #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
# Parts of this file are derived from the Narwhal Devices labscript #
# driver, Copyright (c) 2020 Rory Speirs, which is licensed under   #
# the MIT License. See NARWHAL-DEVICES-MIT-LICENSE.txt in this      #
# directory.                                                        #
#                                                                   #
#####################################################################
"""Narwhal Devices Pulse Generator.

Host software and documentation: https://github.com/Narwhal-Devices/narwhaldevs-pulsegen
"""

import labscript
import numpy as np
from labscript import (
    ClockLine,
    DigitalOut,
    IntermediateDevice,
    LabscriptError,
    Pseudoclock,
    PseudoclockDevice,
    WaitMonitor,
    compiler,
    config,
    set_passed_properties,
)

from .driver import (
    CYCLE,
    MAX_ADDRESS,
    MAX_DURATION,
    MAX_GOTO_COUNTER,
    MAX_POWERLINE_DELAY,
    MAX_TRIGGER_OUT_DELAY,
    MAX_TRIGGER_OUT_LENGTH,
)

N_CHANNELS = 24
MAX_INSTRUCTIONS = MAX_ADDRESS + 1

#: One row per device instruction, in address order. Bit n of `state` is the level
#: of channel n. `duration` is in cycles of 10 ns. The worker fills the channels that
#: the shot does not use from the front panel, and the state of a wait at t=0.
PULSE_PROGRAM_DTYPE = np.dtype(
    [
        ("state", "<u4"),
        ("duration", "<u8"),
        ("goto_address", "<u2"),
        ("goto_counter", "<u4"),
        ("stop_and_wait", "?"),
        ("powerline_sync", "?"),
    ]
)


def parse_channel(connection):
    """The channel number of a connection string 'channel n', or None if the string
    is not of that form with n from 0 to 23."""
    parts = str(connection).split()
    if len(parts) == 2 and parts[0] == "channel" and parts[1].isdigit():
        channel = int(parts[1])
        if channel < N_CHANNELS:
            return channel
    return None


class _NarwhalPseudoclock(Pseudoclock):
    """The pulse generator's pseudoclock. A clockline on it has connection
    'channel n'."""

    def add_device(self, device):
        if isinstance(device, ClockLine) and device.connection != "internal":
            self.parent_device.claim_channel(device)
        Pseudoclock.add_device(self, device)


class _NarwhalDummyPseudoclock(Pseudoclock):
    """Dummy pseudoclock that lets the :class:`~labscript.WaitMonitor` be attached to
    the pulse generator, which measures its own waits."""

    def add_device(self, device):
        if isinstance(device, _NarwhalDummyClockLine) and not self.child_devices:
            Pseudoclock.add_device(self, device)
        else:
            raise LabscriptError(
                f"{self.name} is the internal wait monitor pseudoclock of "
                f"{self.parent_device.name} and cannot have other children."
            )

    def generate_code(self, *args, **kwargs):
        pass


class _NarwhalDummyClockLine(ClockLine):
    def add_device(self, device):
        if isinstance(device, _NarwhalDummyIntermediateDevice) and not self.child_devices:
            ClockLine.add_device(self, device)
        else:
            raise LabscriptError(
                f"{self.name} is the internal wait monitor clockline of "
                f"{self.pseudoclock_device.name} and cannot have other children."
            )

    def generate_code(self, *args, **kwargs):
        pass


class _NarwhalDummyIntermediateDevice(IntermediateDevice):
    def add_device(self, device):
        if isinstance(device, WaitMonitor):
            IntermediateDevice.add_device(self, device)
        else:
            raise LabscriptError(
                f"Only a WaitMonitor can be connected to "
                f"{self.pseudoclock_device.name}.internal_wait_monitor_outputs."
            )

    def generate_code(self, *args, **kwargs):
        pass


class NarwhalPulseGeneratorDirectOutputs(IntermediateDevice):
    """The digital outputs of the pulse generator. A child has connection
    'channel n'."""

    description = "Narwhal Devices Pulse Generator direct outputs"
    allowed_children = [DigitalOut]
    clock_limit = 1 / CYCLE

    def add_device(self, device):
        self.pseudoclock_device.claim_channel(device)
        IntermediateDevice.add_device(self, device)


class NarwhalPulseGenerator(PseudoclockDevice):
    """A Narwhal Devices Pulse Generator: 24 digital channels with a 10 ns cycle and
    8192 instructions.

    Each channel is either a clockline for other devices, created as
    ``ClockLine(name, pulsegen.pseudoclock, 'channel n')``, or a direct output, a
    ``DigitalOut`` or ``Trigger`` with parent ``pulsegen.direct_outputs`` and
    connection ``'channel n'``. Channels that the shot does not use keep their front
    panel values.

    As the master pseudoclock the device measures its own waits and resumes a wait
    that times out, unless ``use_wait_monitor`` is False.
    """

    description = "Narwhal Devices Pulse Generator"
    clock_limit = 1 / CYCLE
    clock_resolution = CYCLE
    trigger_edge_type = "rising"
    trigger_delay = 4 * CYCLE
    trigger_minimum_duration = CYCLE
    minimum_recovery_time = 2 * CYCLE
    wait_delay = 0
    allowed_children = [_NarwhalPseudoclock, _NarwhalDummyPseudoclock]

    @set_passed_properties(
        property_names={
            "connection_table_properties": ["serial_number"],
            "device_properties": [
                "clock_limit",
                "clock_resolution",
                "trigger_delay",
                "trigger_minimum_duration",
                "minimum_recovery_time",
                "wait_delay",
                "trigger_out_length",
                "trigger_out_delay",
                "trigger_on_powerline",
                "powerline_trigger_delay",
            ],
        }
    )
    def __init__(
        self,
        name,
        serial_number=None,
        trigger_device=None,
        trigger_connection=None,
        trigger_out_length=10e-9,
        trigger_out_delay=0,
        trigger_on_powerline=False,
        powerline_trigger_delay=0,
        use_wait_monitor=True,
    ):
        """
        Args:
            name (str): Python variable name of the device.
            serial_number (int, optional): Serial number of the pulse generator. If
                None, the only pulse generator that is connected is used, and an
                error is reported if a port that may have another is in use.
            trigger_device (:class:`~labscript.IntermediateDevice`, optional): Device
                with the digital output that triggers this device when it is a
                secondary pseudoclock.
            trigger_connection (str, optional): The output of ``trigger_device`` that
                is connected to the trigger input.
            trigger_out_length (float, optional): Length in seconds of the pulse on
                the trigger-out port at the start of a run, 0 to 2.55e-6. Zero disables
                the pulse.
            trigger_out_delay (float, optional): Delay in seconds from the start of a
                run to the trigger-out pulse.
            trigger_on_powerline (bool, optional): If True, every trigger, including
                the software trigger that starts the shot and the triggers that end
                waits, takes effect at the next positive zero crossing of the mains
                plus ``powerline_trigger_delay``. The device must have a powerline
                signal on its powerline input.
            powerline_trigger_delay (float, optional): Delay in seconds from a mains
                zero crossing to the powerline trigger, 0 to 41.94303e-3.
            use_wait_monitor (bool, optional): Whether the device measures its own
                waits when it is the master pseudoclock.
        """
        PseudoclockDevice.__init__(self, name, trigger_device, trigger_connection)
        self.serial_number = None if serial_number is None else int(serial_number)
        self.BLACS_connection = "auto" if serial_number is None else str(self.serial_number)
        # Stored in cycles:
        self.trigger_out_length = self._cycles(
            "trigger_out_length", trigger_out_length, MAX_TRIGGER_OUT_LENGTH
        )
        self.trigger_out_delay = self._cycles(
            "trigger_out_delay", trigger_out_delay, MAX_TRIGGER_OUT_DELAY
        )
        self.powerline_trigger_delay = self._cycles(
            "powerline_trigger_delay", powerline_trigger_delay, MAX_POWERLINE_DELAY
        )
        self.trigger_on_powerline = bool(trigger_on_powerline)
        self.use_wait_monitor = use_wait_monitor and self.is_master_pseudoclock
        #: The clockline or direct output on each channel in use.
        self._channel_users = {}
        #: The times of the waits made with `wait_for_powerline`.
        self._powerline_wait_times = set()

        self._pseudoclock = _NarwhalPseudoclock(f"{name}_pseudoclock", self, "clock")
        self._direct_output_clock_line = ClockLine(
            f"{name}_direct_output_clock_line",
            self._pseudoclock,
            "internal",
            ramping_allowed=False,
        )
        self._direct_outputs = NarwhalPulseGeneratorDirectOutputs(
            f"{name}_direct_outputs", self._direct_output_clock_line
        )

        if self.use_wait_monitor:
            dummy_pseudoclock = _NarwhalDummyPseudoclock(
                f"{name}__dummy_wait_pseudoclock", self, "_"
            )
            dummy_clock_line = _NarwhalDummyClockLine(
                f"{name}__dummy_wait_clock_line", dummy_pseudoclock, "_"
            )
            self._wait_monitor_outputs = _NarwhalDummyIntermediateDevice(
                f"{name}_internal_wait_monitor_outputs", dummy_clock_line
            )
            WaitMonitor(
                f"{name}__wait_monitor",
                self._wait_monitor_outputs,
                "internal",
                self._wait_monitor_outputs,
                "internal",
                self._wait_monitor_outputs,
                "internal",
            )

    def _cycles(self, argument, seconds, maximum):
        cycles = int(round(seconds / CYCLE))
        if not 0 <= cycles <= maximum:
            raise LabscriptError(
                f"{self.name}: {argument} must be between 0 and {maximum * CYCLE:.9g} s, "
                f"not {seconds} s."
            )
        return cycles

    @property
    def pseudoclock(self):
        """The internal :class:`~labscript.Pseudoclock`. Connect clocklines to it."""
        return self._pseudoclock

    @property
    def direct_outputs(self):
        """The :class:`NarwhalPulseGeneratorDirectOutputs`. Connect digital outputs
        and triggers to it."""
        return self._direct_outputs

    @property
    def internal_wait_monitor_outputs(self):
        return self._wait_monitor_outputs

    def claim_channel(self, device):
        """Record that a clockline or direct output uses a channel, after checking its
        connection string and that the channel is free."""
        channel = parse_channel(device.connection)
        if channel is None:
            raise LabscriptError(
                f"{device.name} has connection {device.connection!r} to {self.name}. "
                f"The connection must be 'channel n' with n from 0 to {N_CHANNELS - 1}."
            )
        other = self._channel_users.get(channel)
        if other is not None:
            raise LabscriptError(
                f"{device.name} and {other.name} are both connected to channel "
                f"{channel} of {self.name}."
            )
        self._channel_users[channel] = device

    def add_device(self, device):
        if isinstance(device, (_NarwhalPseudoclock, _NarwhalDummyPseudoclock)):
            PseudoclockDevice.add_device(self, device)
        elif isinstance(device, Pseudoclock):
            raise LabscriptError(
                f"{self.name} creates its own Pseudoclock. Connect clocklines to "
                f"{self.name}.pseudoclock instead of creating a Pseudoclock."
            )
        elif isinstance(device, DigitalOut):
            raise LabscriptError(
                f"{device.name} must be connected to {self.name}.direct_outputs, not "
                f"to {self.name}."
            )
        elif isinstance(device, ClockLine):
            raise LabscriptError(
                f"{device.name} must be connected to {self.name}.pseudoclock, not to "
                f"{self.name}."
            )
        else:
            raise LabscriptError(
                f"{self.name} does not support children of class "
                f"{device.__class__.__name__}."
            )

    def wait_for_powerline(self, label, t, timeout=1.0):
        """A :func:`labscript.wait` that ends at the next positive zero crossing of
        the mains plus ``powerline_trigger_delay``, instead of on a trigger. Hardware
        and software triggers are ignored during the wait, so the timeout is not used
        and only has to be longer than one mains period. The wait monitor measures the
        wait like any other. Returns the value of :func:`labscript.wait`."""
        if not self.is_master_pseudoclock:
            raise LabscriptError(
                f"{self.name}.wait_for_powerline() requires {self.name} to be the "
                "master pseudoclock."
            )
        delay = labscript.wait(label, t, timeout)
        self._powerline_wait_times.add(t)
        return delay

    def generate_code(self, hdf5_file):
        PseudoclockDevice.generate_code(self, hdf5_file)
        group = self.init_device_group(hdf5_file)
        program, wait_at_start = self._compile_program()
        group.create_dataset(
            "PULSE_PROGRAM", compression=config.compression, data=program
        )
        used_channels = sum(1 << channel for channel in self._channel_users)
        self.set_property(
            "is_master_pseudoclock",
            self.is_master_pseudoclock,
            location="device_properties",
        )
        self.set_property("stop_time", self.stop_time, location="device_properties")
        self.set_property("used_channels", used_channels, location="device_properties")
        self.set_property("wait_at_start", wait_at_start, location="device_properties")

    def _compile_program(self):
        """The instruction table for the clock instructions of the pseudoclock, and
        whether the shot begins with a wait."""
        # The direct outputs' levels at each tick of the internal clockline:
        n_ticks = len(self.pseudoclock.times[self._direct_output_clock_line])
        direct_states = np.zeros(n_ticks, dtype=np.int64)
        for output in self.direct_outputs.get_all_outputs():
            direct_states = direct_states | (
                output.raw_output.astype(np.int64) << parse_channel(output.connection)
            )
        clock_bits = {
            clockline: 1 << parse_channel(clockline.connection)
            for clockline in self.pseudoclock.child_devices
            if clockline is not self._direct_output_clock_line
        }
        wait_times = sorted(compiler.wait_table)

        # Each row is [state, duration, goto_address, goto_counter, stop_and_wait,
        # powerline_sync]:
        rows = []
        state = 0
        tick = -1
        wait_index = 0
        wait_at_start = False
        powerline_sync = False
        for instruction in self.pseudoclock.clock:
            if instruction == "WAIT":
                powerline_sync = wait_times[wait_index] in self._powerline_wait_times
                wait_index += 1
                if not rows:
                    # The device pauses after an instruction, so the wait at t=0 pauses
                    # after one cycle. The worker sets this cycle's state to the front
                    # panel values, so no output changes before the trigger.
                    wait_at_start = True
                    rows.append([0, 1, 0, 0, True, False])
                elif rows[-1][3]:
                    # The last instruction loops. Split off its last repetition so that
                    # the device pauses once, not at the end of every repetition.
                    high, low = rows[-2], rows[-1]
                    low[3] -= 1
                    rows.append([high[0], high[1], 0, 0, False, False])
                    rows.append([low[0], low[1], 0, 0, True, False])
                else:
                    rows[-1][4] = True
                continue

            step = int(round(instruction["step"] / CYCLE))
            reps = int(instruction["reps"])
            clocks = 0
            for clockline in instruction["enabled_clocks"]:
                if clockline is self._direct_output_clock_line:
                    tick += 1
                    state = int(direct_states[tick])
                else:
                    clocks |= clock_bits[clockline]
            if clocks == 0:
                self._check_duration(step * reps, instruction)
                rows.append([state, step * reps, 0, 0, False, powerline_sync])
            else:
                if step < 2:
                    names = ", ".join(
                        clockline.name for clockline in clock_bits if clocks & clock_bits[clockline]
                    )
                    raise LabscriptError(
                        f"{self.name}: a clock tick of {names} at t={instruction['start']} s "
                        f"has a period of one cycle ({CYCLE} s). A clock tick needs at "
                        f"least two cycles, one high and one low."
                    )
                if reps - 1 > MAX_GOTO_COUNTER:
                    raise LabscriptError(
                        f"{self.name}: a clock instruction at t={instruction['start']} s "
                        f"repeats {reps} times, more than the maximum of "
                        f"{MAX_GOTO_COUNTER + 1}."
                    )
                high = step // 2
                self._check_duration(step - high, instruction)
                first = len(rows)
                rows.append([state | clocks, high, 0, 0, False, powerline_sync])
                rows.append([state, step - high, first, reps - 1, False, False])
            powerline_sync = False

        if len(rows) > MAX_INSTRUCTIONS:
            raise LabscriptError(
                f"{self.name} needs {len(rows)} instructions, more than the maximum of "
                f"{MAX_INSTRUCTIONS}."
            )
        program = np.array([tuple(row) for row in rows], dtype=PULSE_PROGRAM_DTYPE)
        return program, wait_at_start

    def _check_duration(self, cycles, instruction):
        if not 1 <= cycles <= MAX_DURATION:
            raise LabscriptError(
                f"{self.name}: the instruction at t={instruction['start']} s lasts "
                f"{cycles} cycles. An instruction lasts between 1 and {MAX_DURATION} "
                f"cycles of {CYCLE} s."
            )
