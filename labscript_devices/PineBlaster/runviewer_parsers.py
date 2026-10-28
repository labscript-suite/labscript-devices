#####################################################################
#                                                                   #
# /labscript_devices/PineBlaster/runviewer_parsers.py               #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################
from labscript_devices.common.runviewer import rising_edge_times
import numpy as np
import labscript_utils.h5_lock
import h5py
from labscript_devices.PineBlaster.labscript_devices import PineBlaster


 

class RunviewerClass(object):
    clock_resolution = PineBlaster.clock_resolution
    clock_type = PineBlaster.clock_type
    trigger_delay = PineBlaster.trigger_delay
    wait_delay = PineBlaster.wait_delay
    
    def __init__(self, path, device):
        self.path = path
        self.name = device.name
        self.device = device
        
            
    def get_traces(self, add_trace, clock=None):
        if clock is not None:
            clock_ticks = rising_edge_times(clock)

        
            
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
        
        clock = (np.array(time), np.array(states))
        
        clocklines_and_triggers = {}
        for pseudoclock_name, pseudoclock in self.device.child_list.items():
            for clock_line_name, clock_line in pseudoclock.child_list.items():
                if clock_line.parent_port == 'internal':
                    clocklines_and_triggers[clock_line_name] = clock
                    add_trace(clock_line_name, clock, self.name, clock_line.parent_port)
            
        return clocklines_and_triggers
