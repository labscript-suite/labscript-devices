#####################################################################
#                                                                   #
# /labscript_devices/AD9959DDSSweeper/runviewer_parsers.py          #
#                                                                   #
# Copyright 2025, Carter Turnbaugh                                  #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################

import labscript_utils.h5_lock
import h5py
import numpy as np
from labscript_devices.common.runviewer import rising_edge_times

import labscript_utils.properties as properties


class AD9959DDSSweeperParser(object):
    def __init__(self, path, device):
        self.path = path
        self.name = device.name
        self.device = device

    def get_traces(self, add_trace, clock=None):
        if clock is None:
            raise Exception(f'No clock passed to {self.name}. The AD9959DDSSweeper must be clocked by another device.')

        clock_ticks = rising_edge_times(clock)

        subchnls = ['freq', 'amp', 'phase']
        data = {}
        with h5py.File(self.path, 'r') as f:
            if self.name not in f['devices']:
                # The device has no outputs, so generate_code wrote nothing
                return {}
            group = f['devices'][self.name]
            if 'dds_data' in group:
                dds_data = group['dds_data'][()]
                device_props = properties.get(f, self.name, 'device_properties')
                scale_factors = {
                    'freq': device_props['frequency_scale_factor'],
                    'amp': device_props['amplitude_scale_factor'],
                    'phase': device_props['phase_scale_factor'],
                }
                channels = [int(n[4:]) for n in dds_data.dtype.names if n.startswith('freq')]
                for channel in channels:
                    for subchnl in subchnls:
                        values = dds_data[f'{subchnl}{channel}'] / scale_factors[subchnl]
                        data[f'channel {channel}_{subchnl}'] = (clock_ticks, values)
            if 'static_data' in group:
                # Static values are stored in base units, not tuning words
                static_data = group['static_data'][()]
                channels = [int(n[4:]) for n in static_data.dtype.names if n.startswith('freq')]
                for channel in channels:
                    for subchnl in subchnls:
                        values = np.full(len(clock_ticks), static_data[f'{subchnl}{channel}'][0])
                        data[f'channel {channel}_{subchnl}'] = (clock_ticks, values)

        for channel_name, channel in self.device.child_list.items():
            for subchnl_name, subchnl in channel.child_list.items():
                connection = f'{channel.parent_port}_{subchnl.parent_port}'
                if connection in data:
                    add_trace(subchnl.name, data[connection], self.name, connection)

        return {}
