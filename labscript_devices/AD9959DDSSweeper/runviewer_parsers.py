#####################################################################
#                                                                   #
# /labscript_devices/AD9959DDSSweeper/runview_parsers.py            #
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

import labscript_utils.properties as properties

class AD9959DDSSweeperParser(object):
    def __init__(self, path, device):
        self.path = path
        self.name = device.name
        self.device = device

    def get_traces(self, add_trace, clock=None):
        with h5py.File(self.path, "r") as f:
            group = f['devices'][self.name]
            dds_data = group['dds_data'][()]
            channels = set([int(n[4:]) for n in dds_data.dtype.names if n.startswith('freq')])

            dtypes = {'names':['freq%d' % i for i in DDSs] +
                      ['amp%d' % i for i in DDSs] +
                      ['phase%d' % i for i in DDSs],
                      'formats':[np.float for i in DDSs] +
                      [np.float for i in DDSs] + 
                      [np.float for i in DDSs]}

            data = np.zeros(len(dds_data), dtype=dtypes)

            connection_table_props = properties.get(f, self.name, 'connection_table_properties')
            freq_scale = connection_table_props['ref_clock_frequency'] * connection_table_props['pll_mult'] / 2**32
            amp_scale = 1.0 / 1023
            phase_scale = 360.0 / 16384

            for channel in channels:
                data['%d_freq' % channel] = dds_data['freq%d' % channel] * freq_scale
                data['%d_amp' % channel] = dds_data['amp%d' % channel] * amp_scale
                data['%d_phase' % channel] = dds_data['phase%d' % channel] * phase_scale

        for channel_name, channel in self.device.child_list.items():
            for subchnl_name, subchnl in channel.child_list.items():
                connection = '%s_%s' % (channel.parent_port, subchnl.parent_port)
                if connection in data:
                    add_trace(subchnl.name, data[connection], self.name, connection)

        return {}
