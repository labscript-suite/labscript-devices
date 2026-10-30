#####################################################################
#                                                                   #
# /labscript_devices/DummyIntermediateDevice/runviewer_parsers.py   #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from labscript_devices.common.runviewer import rising_edge_times
import labscript_utils.h5_lock
import h5py


class DummyIntermediateDeviceParser(object):
    def __init__(self, path, device):
        self.path = path
        self.name = device.name
        self.device = device

    def get_traces(self, add_trace, clock=None):
        if clock is None:
            raise Exception(f'No clock passed to {self.name}. The DummyIntermediateDevice must be clocked by another device.')

        if not self.device.child_list:
            return {}

        clock_ticks = rising_edge_times(clock)

        with h5py.File(self.path, 'r') as f:
            outputs = f['devices/%s/OUTPUTS' % self.name][:]

        triggers = {}
        for channel_name, channel in self.device.child_list.items():
            trace = (clock_ticks, outputs[channel_name])
            if channel.device_class == 'Trigger':
                triggers[channel_name] = trace
            add_trace(channel_name, trace, self.name, channel.parent_port)

        return triggers
