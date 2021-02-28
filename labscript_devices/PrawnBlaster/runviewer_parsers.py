#####################################################################
#                                                                   #
# /labscript_devices/PrawnBlaster/runviewer_parsers.py              #
#                                                                   #
# Copyright 2021, Philip Starkey                                    #
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


class PrawnBlasterParser(object):
    def __init__(self, path, device):
        self.path = path
        self.name = device.name
        self.device = device

    def get_traces(self, add_trace, clock=None):
        if clock is not None:
            times, clock_value = clock[0], clock[1]
            clock_indices = np.where((clock_value[1:] - clock_value[:-1]) == 1)[0] + 1
            # If initial clock value is 1, then this counts as a rising edge
            # (clock should be 0 before experiment) but this is not picked up
            # by the above code. So we insert it!
            if clock_value[0] == 1:
                clock_indices = np.insert(clock_indices, 0, 0)
            clock_ticks = times[clock_indices]

        # get the pulse program
        pulse_programs = []
        with h5py.File(self.path, 'r') as f:
            # Get the device properties
            device_props = properties.get(f, self.name, 'device_properties')
            conn_props = properties.get(f, self.name, 'connection_table_properties')

            self.clock_resolution = device_props["clock_resolution"]
            self.trigger_delay = device_props["trigger_delay"]
            self.wait_delay = device_props["wait_delay"]

            # Extract the pulse programs
            num_pseudoclocks = conn_props["num_pseudoclocks"]
            for i in range(num_pseudoclocks):
                pulse_programs.append(f[f'devices/{self.name}/PULSE_PROGRAM_{i}'][:])
        
        # Generate clocklines and triggers
        clocklines_and_triggers = {}
        for pulse_program in pulse_programs:
            time = []
            states = []
            trigger_index = 0
            t = 0 if clock is None else clock_ticks[trigger_index] + self.trigger_delay
            trigger_index += 1

            clock_factor = self.clock_resolution / 2.0

            last_instruction_was_wait = False
            for row in pulse_program:
                if row['reps'] == 0 and not last_instruction_was_wait: # WAIT
                    last_instruction_was_wait = True
                    if clock is not None:
                        t = clock_ticks[trigger_index] + self.trigger_delay
                        trigger_index += 1
                    else:
                        t += self.wait_delay
                elif last_instruction_was_wait:
                    # two waits in a row means an indefinite wait, so we just skip this
                    # instruction.
                    last_instruction_was_wait = False
                    continue
                else:
                    last_instruction_was_wait = False
                    for i in range(row['reps']):
                        for j in range(1, -1, -1):
                            time.append(t)
                            states.append(j)
                            t += row['period'] * clock_factor

            clock = (np.array(time), np.array(states))

            for pseudoclock_name, pseudoclock in self.device.child_list.items():
                for clock_line_name, clock_line in pseudoclock.child_list.items():
                    # Ignore the dummy internal wait monitor clockline
                    if clock_line.parent_port.startswith("GPIO"):
                        clocklines_and_triggers[clock_line_name] = clock
                        add_trace(clock_line_name, clock, self.name, clock_line.parent_port)

        return clocklines_and_triggers
