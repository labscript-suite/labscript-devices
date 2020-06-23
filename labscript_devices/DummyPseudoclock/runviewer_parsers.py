import labscript_utils.h5_lock  # noqa: F401
import h5py
import numpy as np


class DummyPseudoclockParser(object):
    clock_resolution = 25e-9
    trigger_delay = 350e-9
    wait_delay = 2.5e-6

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
        with h5py.File(self.path, 'r') as f:
            pulse_program = f[f'devices/{self.name}/PULSE_PROGRAM'][:]

        time = []
        states = []
        trigger_index = 0
        t = 0 if clock is None else clock_ticks[trigger_index] + self.trigger_delay
        trigger_index += 1

        clock_factor = self.clock_resolution / 2.0

        for row in pulse_program:
            if row['period'] == 0:
                # special case
                if row['reps'] == 1:  # WAIT
                    if clock is not None:
                        t = clock_ticks[trigger_index] + self.trigger_delay
                        trigger_index += 1
                    else:
                        t += self.wait_delay
            else:
                for i in range(row['reps']):
                    for j in range(1, -1, -1):
                        time.append(t)
                        states.append(j)
                        t += row['period'] * clock_factor

        clock = (np.array(time), np.array(states))

        clocklines_and_triggers = {}
        for pseudoclock_name, pseudoclock in self.device.child_list.items():
            for clock_line_name, clock_line in pseudoclock.child_list.items():
                if clock_line.parent_port == 'internal':
                    clocklines_and_triggers[clock_line_name] = clock
                    add_trace(clock_line_name, clock, self.name, clock_line.parent_port)

        return clocklines_and_triggers
