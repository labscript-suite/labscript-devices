import labscript_utils.h5_lock
import h5py

class RunviewerClass(object):
    
    def __init__(self, path, device):
        self.path = path
        self.name = device.name
        self.device = device

    def get_traces(self, add_trace, clock=None):

        with h5py.File(self.path, 'r') as f:

            group = f['devices/' + self.name]

            if 'AO' in group:
                analogs = group['AO'][:]
            else:
                analogs = None
                analog_out_channels = []
                
            if 'DIGITAL_OUTS' in f['devices/%s'%self.name]:
                digitals = f['devices/%s/DIGITAL_OUTS'%self.name][:]
            else:
                digitals = []
            
        times, clock_value = clock[0], clock[1]

        clock_indices = np.where((clock_value[1:]-clock_value[:-1])==1)[0]+1
        # If initial clock value is 1, then this counts as a rising edge (clock should be 0 before experiment)
        # but this is not picked up by the above code. So we insert it!
        if clock_value[0] == 1:
            clock_indices = np.insert(clock_indices, 0, 0)
        clock_ticks = times[clock_indices]
        
        traces = {}
        for i in range(self.num_digitals):
            traces['port0/line%d'%i] = []
        for row in digitals:
            bit_string = np.binary_repr(row,self.num_digitals)[::-1]
            for i in range(self.num_digitals):
                traces[self.port_strings[i]].append(int(bit_string[i]))
                
        for i in range(self.num_digitals):
            traces[self.port_strings[i]] = (clock_ticks, np.array(traces[self.port_strings[i]]))
        
        for i, channel in enumerate(analog_out_channels):
            traces[channel.split('/')[-1]] = (clock_ticks, analogs[:,i])
        
        triggers = {}
        for channel_name, channel in self.device.child_list.items():
            if channel.parent_port in traces:
                if channel.device_class == 'Trigger':
                    triggers[channel_name] = traces[channel.parent_port]
                add_trace(channel_name, traces[channel.parent_port], self.name, channel.parent_port)
        
        return triggers
    