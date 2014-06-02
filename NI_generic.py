#####################################################################
#                                                                   #
# /NI_generic.py                                                    #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################
from labscript_devices import RunviewerParser

import numpy as np
import labscript_utils.h5_lock, h5py

    
@RunviewerParser
class RunviewerClass(object):
    num_digitals = 32
    
    def __init__(self, path, name):
        self.path = path
        self.name = name
        
        # We create a lookup table for strings to be used later as dictionary keys.
        # This saves having to evaluate '%d'%i many many times, and makes the _add_pulse_program_row_to_traces method
        # significantly more efficient
        self.port_strings = {} 
        for i in range(self.num_digitals):
            self.port_strings[i] = 'port0/line%d'%i
            
    def get_traces(self,clock=None):
        if clock is None:
            # we're the master pseudoclock, software triggered. So we don't have to worry about trigger delays, etc
            raise Exception('No clock passed to %s. The NI PCIe 6363 must be clocked by another device.'%self.name)
            
        # get the pulse program
        with h5py.File(self.path, 'r') as f:
            if 'ANALOG_OUTS' in f['devices/%s'%self.name]:
                analogs = f['devices/%s/ANALOG_OUTS'%self.name][:]
                analog_out_channels = f['devices/%s'%self.name].attrs['analog_out_channels'].split(', ')
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
         
        return traces
    