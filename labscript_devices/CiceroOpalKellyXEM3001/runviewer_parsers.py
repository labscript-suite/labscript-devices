#####################################################################
#                                                                   #
# /labscript_devices/CiceroOpalKellyXEM3001/runviewer_parsers.py    #
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
import labscript_utils.properties


        
        
 

class RunviewerClass(object):
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
            device_properties = labscript_utils.properties.get(f, self.name, 'device_properties')
            connection_table_properties = labscript_utils.properties.get(f, self.name, 'connection_table_properties')
        
        clock_frequency = connection_table_properties['clock_frequency']

        time = []
        states = []
        trigger_index = 0
        # t = 0 if clock is None else clock_ticks[trigger_index]+device_properties['trigger_delay']
        # trigger_index += 1
        t = 0
               
        for row in pulse_program:
            if row['reps'] == 0: # WAIT
                if clock is not None:
                    t = clock_ticks[trigger_index]+device_properties['trigger_delay']
                    trigger_index += 1
                else:
                    t += device_properties['wait_delay']
            else:    
                for i in range(row['reps']):
                    time.append(t)
                    states.append(1)
                    t += row['on_period']/clock_frequency
                    time.append(t)
                    states.append(0)
                    t += row['off_period']/clock_frequency
        
        clock = (np.array(time), np.array(states))
        
        clocklines_and_triggers = {}
        for pseudoclock_name, pseudoclock in self.device.child_list.items():
            for clock_line_name, clock_line in pseudoclock.child_list.items():
                if clock_line.parent_port == 'Clock Out':
                    clocklines_and_triggers[clock_line_name] = clock
                    add_trace(clock_line_name, clock, self.name, clock_line.parent_port)
            
        return clocklines_and_triggers
