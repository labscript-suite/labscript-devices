#####################################################################
#                                                                   #
# /labscript_devices/NarwhalPulseGenerator/runviewer_parsers.py     #
#                                                                   #
# Copyright 2026, Christopher Billington                            #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
import labscript_utils.h5_lock  # noqa: F401
import h5py
import numpy as np

import labscript_utils.properties as properties

from labscript_devices.common.runviewer import rising_edge_times
from .labscript_devices import parse_channel


class NarwhalPulseGeneratorParser(object):
    """Runviewer parser for the Narwhal Devices Pulse Generator."""

    def __init__(self, path, device):
        self.path = path
        self.name = device.name
        self.device = device

    def get_traces(self, add_trace, clock=None):
        with h5py.File(self.path, "r") as f:
            props = properties.get(f, self.name, "device_properties")
            program = f[f"devices/{self.name}/PULSE_PROGRAM"][:]
        cycle = props["clock_resolution"]
        times, states = self._expand(program, cycle, props["trigger_delay"], clock)

        pseudoclock = [
            child for child in self.device.child_list.values() if child.parent_port == "clock"
        ][0]
        clocklines_and_triggers = {}
        for clockline in pseudoclock.child_list.values():
            if clockline.parent_port == "internal":
                for direct_outputs in clockline.child_list.values():
                    for output in direct_outputs.child_list.values():
                        trace = (times, (states >> parse_channel(output.parent_port)) & 1)
                        add_trace(output.name, trace, direct_outputs.name, output.parent_port)
                        if output.device_class == "Trigger":
                            clocklines_and_triggers[output.name] = trace
            else:
                trace = (times, (states >> parse_channel(clockline.parent_port)) & 1)
                add_trace(clockline.name, trace, self.name, clockline.parent_port)
                clocklines_and_triggers[clockline.name] = trace
        return clocklines_and_triggers

    def _expand(self, program, cycle, trigger_delay, clock):
        """The time in seconds at which each instruction of the run starts, with
        looping instructions repeated, and the state of each.

        For a secondary device, the run starts and resumes after each wait at the
        rising edges of `clock` plus the trigger delay. For the master, waits have zero
        length."""
        address = np.arange(len(program))
        duration = program["duration"].astype(np.int64)
        state = program["state"].astype(np.int64)
        counter = program["goto_counter"].astype(np.int64)
        # A looping instruction is the low half of a clock tick and jumps back to the
        # preceding instruction, the high half. Both are one row.
        loops = counter > 0
        if (program["goto_address"][loops] != address[loops] - 1).any():
            raise ValueError(f"{self.name}: a loop spans more than two instructions")
        is_low = loops
        is_high = np.concatenate([loops[1:], [False]])
        is_row = ~is_low
        first = address[is_row]
        last = np.where(is_high, address + 1, address)[is_row]
        reps = counter[last] + 1
        n_instructions = np.where(is_high[is_row], 2, 1)
        period = np.where(is_high[is_row], duration[first] + duration[last], duration[first])
        row_start = np.cumsum(period * reps) - period * reps
        # The wait after a row pauses the run before the next row:
        segment = np.cumsum(np.concatenate([[0], program["stop_and_wait"][last][:-1]]))

        # Repeat each row for its repetitions:
        rows = np.repeat(np.arange(len(first)), reps)
        repetition = np.arange(len(rows)) - np.repeat(np.cumsum(reps) - reps, reps)
        rep_start = row_start[rows] + repetition * period[rows]
        # Each repetition is one or two instructions:
        count = n_instructions[rows]
        index = np.repeat(np.arange(len(rows)), count)
        second = np.arange(len(index)) - np.repeat(np.cumsum(count) - count, count)
        start = rep_start[index] + second * duration[first][rows][index]
        instruction = np.where(second == 0, first[rows][index], last[rows][index])
        states = state[instruction]
        segments = segment[rows][index]

        n_segments = int(segment[-1]) + 1 if len(segment) else 0
        segment_start = row_start[np.searchsorted(segment, np.arange(n_segments))]
        if clock is None:
            offset = np.zeros(n_segments)
        else:
            rising = rising_edge_times(clock)
            if len(rising) < n_segments:
                raise ValueError(
                    f"{self.name} starts {n_segments} times (once, then after each "
                    f"wait), but its trigger has {len(rising)} rising edges."
                )
            offset = rising[:n_segments] + trigger_delay - segment_start * cycle
        times = start * cycle + offset[segments]
        return times, states
