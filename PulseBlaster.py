#####################################################################
#                                                                   #
# /PulseBlaster.py                                                  #
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

class x(object):
    pass

import time

profiles = {}
def profile(funct):
    func = funct.__name__
    if func not in profiles:
        profiles[func] = {'total_time':0, 'min':None, 'max':0, 'num_calls':0, 'average_time_per_call':0}
    
    def new_func(*args,**kwargs):
        start_time = time.time()
        ret = funct(*args,**kwargs)
        runtime = time.time()-start_time
        profiles[func]['total_time'] += runtime
        profiles[func]['num_calls'] += 1
        profiles[func]['min'] = profiles[func]['min'] if profiles[func]['min'] is not None and profiles[func]['min'] < runtime else runtime
        profiles[func]['max'] = profiles[func]['max'] if profiles[func]['max'] > runtime else runtime
        profiles[func]['average_time_per_call'] = profiles[func]['total_time']/profiles[func]['num_calls']
        
        return ret
    # return new_func
    return funct
    
def start_profile(name):
    if name not in profiles:
        profiles[name] = {'total_time':0, 'min':None, 'max':0, 'num_calls':0, 'average_time_per_call':0}
        
    if 'start_time' in profiles[name]:
        raise Exception('You cannot call start_profile for %s without first calling stop_profile'%name)
        
    profiles[name]['start_time'] = time.time()
    
def stop_profile(name):
    if name not in profiles or 'start_time' not in profiles[name]:
        raise Exception('You must first call start_profile for %s before calling stop_profile')
        
    runtime = time.time()-profiles[name]['start_time']
    del profiles[name]['start_time']
    profiles[name]['total_time'] += runtime
    profiles[name]['num_calls'] += 1
    profiles[name]['min'] = profiles[name]['min'] if profiles[name]['min'] is not None and profiles[name]['min'] < runtime else runtime
    profiles[name]['max'] = profiles[name]['max'] if profiles[name]['max'] > runtime else runtime
    profiles[name]['average_time_per_call'] = profiles[name]['total_time']/profiles[name]['num_calls']
          
    
@RunviewerParser
class MyRunviewerClass(object):
    num_dds = 2
    num_flags = 12
    
    def __init__(self, path, name):
        self.path = path
        self.name = name
        
        # We create a lookup table for strings to be used later as dictionary keys.
        # This saves having to evaluate '%d'%i many many times, and makes the _add_pulse_program_row_to_traces method
        # significantly more efficient
        self.dds_strings = {}
        for i in range(self.num_dds):
            self.dds_strings[i] = {}
            self.dds_strings[i]['ddsfreq'] = 'dds %d_freq'%i
            self.dds_strings[i]['ddsamp'] = 'dds %d_amp'%i
            self.dds_strings[i]['ddsphase'] = 'dds %d_phase'%i
            self.dds_strings[i]['freq'] = 'freq%d'%i
            self.dds_strings[i]['amp'] = 'amp%d'%i
            self.dds_strings[i]['phase'] = 'phase%d'%i
            self.dds_strings[i]['dds_en'] = 'dds_en%d'%i
            
        self.flag_strings = {}
        self.flag_powers = {}
        
        for i in range(self.num_flags):
            self.flag_strings[i] = 'flag %d'%i
            self.flag_powers[i] = 2**i
        
            
        
    def get_traces(self,parent=None):
        if parent is None:
            # we're the master pseudoclock, software triggered. So we don't have to worry about trigger delays, etc
            pass
            
        # get the pulse program
        with h5py.File(self.path, 'r') as f:
            pulse_program = f['devices/%s/PULSE_PROGRAM'%self.name][:]
            dds = {}
            for i in range(self.num_dds):
                dds[i] = {}
                for reg in ['FREQ', 'AMP', 'PHASE']:
                    dds[i][reg] = f['devices/%s/DDS%d/%s_REGS'%(self.name, i, reg)][:]
        
        clock = []
        traces = {}
        for i in range(self.num_flags):
            traces['flag %d'%i] = []
        for i in range(self.num_dds):
            for sub_chnl in ['freq', 'amp', 'phase']:
                traces['dds %d_%s'%(i,sub_chnl)] = []   
        
        # now build the traces
        t = 0. # TODO: Offset by initial trigger of parent
        i = 0
        while i < len(pulse_program):
            # ignore the first 2 instructions, they are dummy instructions for BLACS
            if i < 2:
                i += 1
                continue
            
            row = pulse_program[i]
            
            if row['inst'] == 2: # Loop
                loops = int(row['inst_data'])
                
                buffer = {}
                j = i
                while loops > 0:
                    looping = True
                    while looping:
                        row = pulse_program[j]
                        # buffer the index of traces used for this instruction
                        # Cuts the runtime down by ~60%
                        # start_profile('loop_contents')
                        if j not in buffer:
                            clock.append(t)
                            self._add_pulse_program_row_to_traces(traces, row, dds)
                            buffer[j] = len(clock)-1
                        else:                            
                            clock.append(t)
                            self._add_pulse_program_row_from_buffer(traces, buffer[j])
                        # stop_profile('loop_contents')
                            
                        # start_profile('end_of_loop')
                        t+= row['length']*1.0e-9
                        
                        if row['inst'] == 3: # END_LOOP
                            looping = False
                            # print 'end loop. j=%d, t=%.7f'%(j,t)
                            j = int(row['inst_data']) if loops > 1 else j
                            # print 'setting j=%d'%j
                        else:
                            # print 'in loop. j=%d, t=%.7f'%(j,t)
                            j+=1
                        # stop_profile('end_of_loop')
                    loops -= 1
                    
                i = j
                # print 'i now %d'%i
                    
            else: # Continue
                if row['inst'] == 8: #WAIT
                    # print 'Wait at %.9f'%t
                    pass
                clock.append(t)
                self._add_pulse_program_row_to_traces(traces,row,dds)
                t+= row['length']*1.0e-9
            
                if row['inst'] == 8: #WAIT
                    #TODO: Offset next time by trigger delay is not master pseudoclock
                    pass
            
            i += 1            
                
        # print 'Stop time: %.9f'%t 
        # now put together the traces
        to_return = {}
        clock = np.array(clock, dtype=np.float64)
        for name, data in traces.items():
            to_return[name] = (clock, np.array(data))
            
        return to_return
    
    @profile
    def _add_pulse_program_row_from_buffer(self, traces, index):
        for i in range(self.num_flags):
            traces[self.flag_strings[i]].append(traces[self.flag_strings[i]][index])
            
        for i in range(self.num_dds):
            current_strings = self.dds_strings[i]
            traces[current_strings['ddsfreq']].append(traces[current_strings['ddsfreq']][index])
            traces[current_strings['ddsphase']].append(traces[current_strings['ddsphase']][index])
            traces[current_strings['ddsamp']].append(traces[current_strings['ddsamp']][index])
            
    @profile            
    def _add_pulse_program_row_to_traces(self, traces, row, dds, flags = None):
        # add flags
        if flags is None:
            flags = np.binary_repr(row['flags'],self.num_flags)[::-1]
        for i in range(self.num_flags):
            traces[self.flag_strings[i]].append(int(flags[i]))
        
        # Below block saved for history. This is much slower compared to what is below!
        # for i in range(self.num_dds):
            # traces['dds %d_freq'%i].append(dds[i]['FREQ'][row['freq%d'%i]])
            # traces['dds %d_phase'%i].append(dds[i]['PHASE'][row['phase%d'%i]])
            # amp = dds[i]['AMP'][row['amp%d'%i]] if row['dds_en%d'%i] else 0
            # traces['dds %d_amp'%i].append(amp)
            
       
        # note that we are looking up keys for the traces dictionary and row array in self.dds_strings
        # Doing this reduces the runtime (of the below block) by 25%
        for i in range(self.num_dds):
            # Note: This is done to reduce runtime (about 10%)
            current_strings = self.dds_strings[i]
            current_dds = dds[i]
            
            traces[current_strings['ddsfreq']].append(current_dds['FREQ'][row[current_strings['freq']]])
            traces[current_strings['ddsphase']].append(current_dds['PHASE'][row[current_strings['phase']]])
            # Note: Using the inline if statement reduces the runtime (of this for loop) by 50%
            amp = current_dds['AMP'][row[current_strings['amp']]] if row[current_strings['dds_en']] else 0
            traces[current_strings['ddsamp']].append(amp)
            
            