import numpy as np
from labscript_devices import runviewer_parser
from labscript import IntermediateDevice, AnalogOut, DigitalOut, AnalogIn, bitfield, config, LabscriptError
import labscript_utils.h5_lock, h5py

class NIBoard(IntermediateDevice):
    allowed_children = [AnalogOut, DigitalOut, AnalogIn]
    n_analogs = 4
    n_digitals = 32
    digital_dtype = np.uint32
    clock_limit = 500e3 # underestimate I think.
    description = 'generic_NI_Board'
    
    def __init__(self, name, parent_device, clock_terminal, MAX_name=None, acquisition_rate=0):
        IntermediateDevice.__init__(self, name, parent_device)
        self.acquisition_rate = acquisition_rate
        self.clock_terminal = clock_terminal
        self.MAX_name = name if MAX_name is None else MAX_name
        self.BLACS_connection = self.MAX_name
        
    def add_device(self,output):
        # TODO: check there are no duplicates, check that connection
        # string is formatted correctly.
        IntermediateDevice.add_device(self,output)
        
    def convert_bools_to_bytes(self,digitals):
        """converts digital outputs to an array of bitfields stored
        as self.digital_dtype"""
        outputarray = [0]*self.n_digitals
        for output in digitals:
            port, line = output.connection.replace('port','').replace('line','').split('/')
            port, line  = int(port),int(line)
            if port > 0:
                raise LabscriptError('Ports > 0 on NI Boards not implemented. Please use port 0, or file a feature request at redmine.physics.monash.edu.au/labscript.')
            outputarray[line] = output.raw_output
        bits = bitfield(outputarray,dtype=self.digital_dtype)
        return bits
            
    def generate_code(self, hdf5_file):
        IntermediateDevice.generate_code(self, hdf5_file)
        analogs = {}
        digitals = {}
        inputs = {}
        for device in self.child_devices:
            if isinstance(device,AnalogOut):
                analogs[device.connection] = device
            elif isinstance(device,DigitalOut):
                digitals[device.connection] = device
            elif isinstance(device,AnalogIn):
                inputs[device.connection] = device
            else:
                raise Exception('Got unexpected device.')
        
        clockline = self.parent_device
        pseudoclock = clockline.parent_device
        times = pseudoclock.times[clockline]
                
        analog_out_table = np.empty((len(times),len(analogs)), dtype=np.float32)
        analog_connections = analogs.keys()
        analog_connections.sort()
        analog_out_attrs = []
        for i, connection in enumerate(analog_connections):
            output = analogs[connection]
            if any(output.raw_output > 10 )  or any(output.raw_output < -10 ):
                # Bounds checking:
                raise LabscriptError('%s %s '%(output.description, output.name) +
                                  'can only have values between -10 and 10 Volts, ' + 
                                  'the limit imposed by %s.'%self.name)
            analog_out_table[:,i] = output.raw_output
            analog_out_attrs.append(self.MAX_name +'/'+connection)
        input_connections = inputs.keys()
        input_connections.sort()
        input_attrs = []
        acquisitions = []
        for connection in input_connections:
            input_attrs.append(self.MAX_name+'/'+connection)
            for acq in inputs[connection].acquisitions:
                acquisitions.append((connection,acq['label'],acq['start_time'],acq['end_time'],acq['wait_label'],acq['scale_factor'],acq['units']))
        # The 'a256' dtype below limits the string fields to 256
        # characters. Can't imagine this would be an issue, but to not
        # specify the string length (using dtype=str) causes the strings
        # to all come out empty.
        acquisitions_table_dtypes = [('connection','a256'), ('label','a256'), ('start',float),
                                     ('stop',float), ('wait label','a256'),('scale factor',float), ('units','a256')]
        acquisition_table= np.empty(len(acquisitions), dtype=acquisitions_table_dtypes)
        for i, acq in enumerate(acquisitions):
            acquisition_table[i] = acq
        digital_out_table = []
        if digitals:
            digital_out_table = self.convert_bools_to_bytes(digitals.values())
        grp = hdf5_file.create_group('/devices/'+self.name)
        if all(analog_out_table.shape): # Both dimensions must be nonzero
            analog_dataset = grp.create_dataset('ANALOG_OUTS',compression=config.compression,data=analog_out_table)
            grp.attrs['analog_out_channels'] = ', '.join(analog_out_attrs)
        if len(digital_out_table): # Table must be non empty
            digital_dataset = grp.create_dataset('DIGITAL_OUTS',compression=config.compression,data=digital_out_table)
            grp.attrs['digital_lines'] = '/'.join((self.MAX_name,'port0','line0:%d'%(self.n_digitals-1)))
        if len(acquisition_table): # Table must be non empty
            input_dataset = grp.create_dataset('ACQUISITIONS',compression=config.compression,data=acquisition_table)
            grp.attrs['analog_in_channels'] = ', '.join(input_attrs)
            grp.attrs['acquisition_rate'] = self.acquisition_rate
        grp.attrs['clock_terminal'] = self.clock_terminal
        
        
@runviewer_parser
class RunviewerClass(object):
    num_digitals = 32
    
    def __init__(self, path, device):
        self.path = path
        self.name = device.name
        self.device = device
        
        # We create a lookup table for strings to be used later as dictionary keys.
        # This saves having to evaluate '%d'%i many many times, and makes the _add_pulse_program_row_to_traces method
        # significantly more efficient
        self.port_strings = {} 
        for i in range(self.num_digitals):
            self.port_strings[i] = 'port0/line%d'%i
            
    def get_traces(self, add_trace, clock=None):
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
        
        triggers = {}
        for channel_name, channel in self.device.child_list.items():
            if channel.parent_port in traces:
                if channel.device_class == 'Trigger':
                    triggers[channel_name] = traces[channel.parent_port]
                add_trace(channel_name, traces[channel.parent_port], self.name, channel.parent_port)
        
        return triggers
    
