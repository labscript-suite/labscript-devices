#####################################################################
#                                                                   #
# /labscript_devices/NovaTechDDS9M/runviewer_parsers.py             #
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
        if clock is None:
            # we're the master pseudoclock, software triggered. So we don't have to worry about trigger delays, etc
            raise Exception('No clock passed to %s. The NovaTechDDS9M must be clocked by another device.'%self.name)
        
        clock_ticks = rising_edge_times(clock)
        
        # get the data out of the H5 file
        data = {}
        with h5py.File(self.path, 'r') as hdf5_file:
            if 'TABLE_DATA' in hdf5_file['devices/%s' % self.name]:
                table_data = hdf5_file['devices/%s/TABLE_DATA' % self.name][:]
                connection_table_properties = labscript_utils.properties.get(hdf5_file, self.name, 'connection_table_properties')
                update_mode = connection_table_properties.get('update_mode', 'synchronous')
                synchronous_first_line_repeat = connection_table_properties.get('synchronous_first_line_repeat', False)
                if update_mode == 'asynchronous' or synchronous_first_line_repeat:
                    table_data = table_data[1:]
                for i in range(2):
                    for sub_chnl in ['freq', 'amp', 'phase']:
                        data['channel %d_%s'%(i,sub_chnl)] = table_data['%s%d'%(sub_chnl,i)][:]
                                
            if 'STATIC_DATA' in hdf5_file['devices/%s'%self.name]:
                static_data = hdf5_file['devices/%s/STATIC_DATA'%self.name][:]
                for i in range(2,4):
                    for sub_chnl in ['freq', 'amp', 'phase']:
                        data['channel %d_%s'%(i,sub_chnl)] = np.empty((len(clock_ticks),))
                        data['channel %d_%s'%(i,sub_chnl)].fill(static_data['%s%d'%(sub_chnl,i)][0])
            
        
        for channel, channel_data in data.items():
            data[channel] = (clock_ticks, channel_data)
        
        for channel_name, channel in self.device.child_list.items():
            for subchnl_name, subchnl in channel.child_list.items():
                connection = '%s_%s'%(channel.parent_port, subchnl.parent_port)
                if connection in data:
                    add_trace(subchnl.name, data[connection], self.name, connection)
        
        return {}
