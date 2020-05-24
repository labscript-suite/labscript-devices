import labscript_utils.h5_lock
import h5py
import numpy as np

import labscript_utils.properties as properties
from labscript_utils import dedent


class NI_DAQmxParser(object):
    def __init__(self, path, device):
        self.path = path
        self.name = device.name
        self.device = device

    def get_traces(self, add_trace, clock=None):

        with h5py.File(self.path, 'r') as f:

            group = f['devices/' + self.name]

            if 'AO' in group:
                AO_table = group['AO'][:]
            else:
                AO_table = None

            if 'DO' in f['devices/%s' % self.name]:
                DO_table = group['DO'][:]
            else:
                DO_table = None

            props = properties.get(f, self.name, 'connection_table_properties')

            version = props.get('__version__', None)
            if version is None:
                msg = """Shot was compiled with the old version of the NI_DAQmx device
                    class. The new runviewer parser is not backward compatible with old
                    shot files. Either downgrade labscript_devices to 2.2.0 or less, or
                    recompile the shot with labscript_devices 2.3.0 or greater."""
                raise RuntimeError(dedent(msg))

            ports = props['ports']
            static_AO = props['static_AO']
            static_DO = props['static_DO']

        times, clock_value = clock[0], clock[1]

        clock_indices = np.where((clock_value[1:] - clock_value[:-1]) == 1)[0] + 1
        # If initial clock value is 1, then this counts as a rising edge (clock should
        # be 0 before experiment) but this is not picked up by the above code. So we
        # insert it!
        if clock_value[0] == 1:
            clock_indices = np.insert(clock_indices, 0, 0)
        clock_ticks = times[clock_indices]

        traces = {}

        if DO_table is not None:
            ports_in_use = DO_table.dtype.names
            for port_str in ports_in_use:
                for line in range(ports[port_str]["num_lines"]):
                    # Extract each digital value from the packed bits:
                    line_vals = (((1 << line) & DO_table[port_str]) != 0).astype(float)
                    if static_DO:
                        line_vals = np.full(len(clock_ticks), line_vals[0])
                    traces['%s/line%d' % (port_str, line)] = (clock_ticks, line_vals)

        if AO_table is not None:
            for chan in AO_table.dtype.names:
                vals = AO_table[chan]
                if static_AO:
                    vals = np.full(len(clock_ticks), vals[0])
                traces[chan] = (clock_ticks, vals)

        triggers = {}
        for channel_name, channel in self.device.child_list.items():
            if channel.parent_port in traces:
                trace = traces[channel.parent_port]
                if channel.device_class == 'Trigger':
                    triggers[channel_name] = trace
                add_trace(channel_name, trace, self.name, channel.parent_port)

        return triggers
