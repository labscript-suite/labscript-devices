#####################################################################
#                                                                   #
# /naqslab_devices/NovaTechDDS/runviewer_parser.py                  #
#                                                                   #
# Copyright 2018, David Meyer                                       #
#                                                                   #
# This file is part of naqslab_devices,                             #
# and is licensed under the                                         #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
# Source borrows heavily from labscript_devices/NovaTechDDS9m       #
#                                                                   #
#####################################################################
import numpy as np
import labscript_utils.h5_lock, h5py
       
        
class NovaTech409B_ACParser(object):    
    def __init__(self, path, device):
        self.path = path
        self.name = device.name
        self.device = device
        self.dyn_chan = [0,1]
        self.static_chan = [2,3]
            
    def get_traces(self, add_trace, clock=None):
        if clock is None:
            # we're the master pseudoclock, software triggered. So we don't have to worry about trigger delays, etc
            raise Exception('No clock passed to %s. A NovaTechDDS must be clocked by another device.' % self.name)
        
        times, clock_value = clock[0], clock[1]
        
        clock_indices = np.where((clock_value[1:]-clock_value[:-1])==1)[0]+1
        # If initial clock value is 1, then this counts as a rising edge (clock should be 0 before experiment)
        # but this is not picked up by the above code. So we insert it!
        if clock_value[0] == 1:
            clock_indices = np.insert(clock_indices, 0, 0)
        clock_ticks = times[clock_indices]
        
        # get the data out of the H5 file
        data = {}
        with h5py.File(self.path, 'r') as hdf5_file:
            if 'TABLE_DATA' in hdf5_file['devices/%s' % self.name]:
                table_data = hdf5_file['devices/%s/TABLE_DATA' % self.name][:]
                connection_table_properties = labscript_utils.properties.get(hdf5_file, self.name, 'connection_table_properties')
                update_mode = getattr(connection_table_properties, 'update_mode', 'synchronous')
                synchronous_first_line_repeat = getattr(connection_table_properties, 'synchronous_first_line_repeat', False)
                if update_mode == 'asynchronous' or synchronous_first_line_repeat:
                    table_data = table_data[1:]
                for i in self.dyn_chan:
                    for sub_chnl in ['freq', 'amp', 'phase']:
                        data['channel %d_%s' % (i,sub_chnl)] = table_data['%s%d' % (sub_chnl,i)][:]
                                
            if 'STATIC_DATA' in hdf5_file['devices/%s' % self.name]:
                static_data = hdf5_file['devices/%s/STATIC_DATA' % self.name][:]
                num_chan = len(static_data)//3
                channels = [int(name[-1]) for name in static_data.dtype.names[0:num_chan]]
                for i in channels:
                    for sub_chnl in ['freq', 'amp', 'phase']:
                        data['channel %d_%s' % (i,sub_chnl)] = np.empty((len(clock_ticks),))
                        data['channel %d_%s' % (i,sub_chnl)].fill(static_data['%s%d' % (sub_chnl,i)][0])
            
        
        for channel, channel_data in data.items():
            data[channel] = (clock_ticks, channel_data)
        
        for channel_name, channel in self.device.child_list.items():
            for subchnl_name, subchnl in channel.child_list.items():
                connection = '%s_%s' % (channel.parent_port, subchnl.parent_port)
                if connection in data:
                    add_trace(subchnl.name, data[connection], self.name, connection)
        
        return {}
    
class NovaTech409BParser(NovaTech409B_ACParser):    
    def __init__(self, path, device):
        NovaTech409B_ACParser.__init__(self,path,device)
        self.dyn_chan = []
        self.static_chan = [0,1,2,3]
        
class NovaTech440AParser(NovaTech409B_ACParser):
    def __init__(self, path, device):
        NovaTech409B_ACParser.__init__(self,path,device)
        self.dyn_chan = []
        self.static_chan = [0]
