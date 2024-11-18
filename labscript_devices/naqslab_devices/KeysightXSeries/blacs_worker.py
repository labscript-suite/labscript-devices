#####################################################################
#                                                                   #
# /naqslab_devices/KeysightXSeries/blacs_worker.py                  #
#                                                                   #
# Copyright 2018, David Meyer                                       #
#                                                                   #
# This file is part of the naqslab devices extension to the         #
# labscript_suite. It is licensed under the Simplified BSD License. #
#                                                                   #
#                                                                   #
#####################################################################
import numpy as np
from naqslab_devices.VISA.blacs_worker import VISAWorker
from labscript import LabscriptError
import labscript_utils.properties

import labscript_utils.h5_lock, h5py

class KeysightXScopeWorker(VISAWorker):   
    # define instrument specific read and write strings
    setup_string = '*ESE 60;*SRE 32;*CLS;:WAV:BYT MSBF;UNS ON;POIN:MODE RAW'
    # *ESE does not disable bits in ESR, just their reporting to STB
    # need to use our own mask
    esr_mask = 60
    # note that analog & digital channels require different :WAV:FORM commands
    read_analog_parameters_string = ':WAV:FORM WORD;SOUR CHAN{0:d};PRE?'
    read_dig_parameters_string = ':WAV:FORM BYTE;SOUR POD{0:d};PRE?'
    read_waveform_string = ':WAV:DATA?'
    read_counter_string = ':MEAS:{0:s}{1:s}? CHAN{2:d}'
    model_ident = ['SO-X','SOX']
    # some devices need the alternative :SING command, checked for in init()
    dig_command = ':DIG'
    
    def analog_waveform_parser(self,raw_waveform_array,y0,dy,yoffset):
        '''Parses the numpy array from the analog waveform query.'''
        return (raw_waveform_array - yoffset)*dy + y0
        
    def digital_pod_parser(self,raw_pod_array):
        '''Unpacks the bits for a pod array
        Columns returned are in bit order [7,6,5,4,3,2,1,0]'''
        return np.unpackbits(raw_pod_array.astype(np.uint8),axis=0).reshape((-1,8),order='C')
        
    def error_parser(self,error_return_string):
        '''Parses the strings returned by :SYST:ERR?
        Returns int_code, err_string'''
        return int(error_return_string.split(',')[0]), error_return_string        
    
    def init(self):
        # Call the VISA init to initialise the VISA connection
        VISAWorker.init(self)
        # Override the timeout for longer scope waits
        self.connection.timeout = 10000
        
        # Query device name to ensure supported scope
        ident_string = self.connection.query('*IDN?')
        if ('KEYSIGHT' in ident_string) and any(sub in ident_string for sub in self.model_ident):
            # Scope supported!
            # If scope is a DSO-X 1000 series, need to use alternate digitize_command for some reason
            if 'DSO-X 1' in ident_string:
                self.dig_command = ':SING'
        else:
            raise LabscriptError('Device {0:s} with VISA name {0:s} not supported!'.format(ident_string,self.VISA_name))  
        
        # initialization stuff
        self.connection.write(self.setup_string)
        # initialize smart cache
        self.smart_cache = {'COUNTERS': None}            
        
    def transition_to_buffered(self,device_name,h5file,initial_values,fresh):
        '''This configures counters, if any are defined, 
        as well as optional compression options for saved data traces.'''
        VISAWorker.transition_to_buffered(self,device_name,h5file,initial_values,fresh)
        
        data = None
        refresh = False
        send_trigger = False
        with h5py.File(h5file,'r') as hdf5_file:
            group = hdf5_file['/devices/'+device_name]
            device_props = labscript_utils.properties.get(hdf5_file,device_name,'device_properties')
            if 'COUNTERS' in group:
                data = group['COUNTERS'][:]
            if len(group):
                send_trigger = True
            # get trace compression options
            self.comp_settings = {'compression':device_props['compression'],
                            'compression_opts':device_props['compression_opts'],
                            'shuffle':device_props['shuffle']}

        if data is not None:
            #check if refresh needed
            if not fresh:
                try:
                    refresh = not np.all(np.equal(data,self.smart_cache['COUNTERS']))
                except ValueError:
                    # arrays not of same size
                    refresh = True
            if fresh or refresh:
                for connection,typ,pol in data:
                    chan_num = int(connection.split(' ')[-1])
                    self.connection.write(':MEAS:{0:s}{1:s} CHAN{2:d}'.format(pol,typ,chan_num))
                    
                    self.smart_cache['COUNTERS'] = data
        
        if send_trigger:            
            # put scope into single mode
            # necessary since :WAV:DATA? clears data and wait for fresh data
            # when in continuous run mode
            self.connection.write(self.dig_command)
        
        return self.final_values        
            
    def transition_to_manual(self,abort = False):
        if not abort:         
            with h5py.File(self.h5_file,'r') as hdf5_file:
                # get acquisitions table values so we can close the file
                try:
                    location = '/devices/'+self.device_name+'/ANALOG_ACQUISITIONS'
                    analog_acquisitions = hdf5_file[location][()]
                    trigger_time = hdf5_file[location].attrs['trigger_time']
                except:
                    # No analog acquisitions!
                    analog_acquisitions = np.empty(0)
                try:
                    location = '/devices/'+self.device_name+'/POD1_ACQUISITIONS'
                    pod1_acquisitions = hdf5_file[location][()]
                    trigger_time = hdf5_file[location].attrs['trigger_time']
                except:
                    # No acquisitions in first digital Pod
                    pod1_acquisitions = np.empty(0)
                try:
                    location = '/devices/'+self.device_name+'/POD2_ACQUISITIONS'
                    pod2_acquisitions = hdf5_file[location][()]
                    trigger_time = hdf5_file[location].attrs['trigger_time']
                except:
                    # No acquisitions in second digital Pod
                    pod2_acquisitions = np.empty(0)
                try:
                    location = '/devices/'+self.device_name+'/COUNTERS'
                    counters = hdf5_file[location][()]
                    trigger_time = hdf5_file[location].attrs['trigger_time']
                except:
                    # no counters
                    counters = np.empty(0)
                # return if no acquisitions at all
                if not len(analog_acquisitions) and not len(pod1_acquisitions) and not len(pod2_acquisitions) and not len(counters):
                    return True
            # close lock on h5 to read from scope, it takes a while
            
            data = {}
            # read analog channels if they exist
            if len(analog_acquisitions):          
                for connection,label in analog_acquisitions:
                    channel_num = int(connection.decode('UTF-8').split(' ')[-1])
                    # read an analog channel
                    # use larger chunk size for faster large data reads
                    [form,typ,Apts,cnt,Axinc,Axor,Axref,yinc,yor,yref] = self.connection.query_ascii_values(self.read_analog_parameters_string.format(channel_num))
                    if Apts*2+11 >= 400000:   # Note that +11 accounts for IEEE488.2 waveform header, not true in unicode (ie Python 3+)
                        default_chunk = self.connection.chunk_size
                        self.connection.chunk_size = int(Apts*2+11)
                    raw_data = self.connection.query_binary_values(self.read_waveform_string,datatype='H', is_big_endian=True, container=np.array)
                    if Apts*2+11 >= 400000:
                        self.connection.chunk_size = default_chunk
                    data[connection] = self.analog_waveform_parser(raw_data,yor,yinc,yref)
                # create the time array
                data['Analog Time'] = np.arange(Axref,Axref+Apts,1,dtype=np.float64)*Axinc + Axor
           
            # read pod 1 channels if necessary     
            if len(pod1_acquisitions):
                # use larger chunk size for faster large data reads
                [form,typ,Dpts,cnt,Dxinc,Dxor,Dxref,yinc,yor,yref] = self.connection.query_ascii_values(self.read_dig_parameters_string.format(1))
                if Dpts+11 >= 400000:
                    default_chunk = self.connection.chunk_size
                    self.connection.chunk_size = int(Dpts+11)
                raw_data = self.connection.query_binary_values(self.read_waveform_string,datatype='B',is_big_endian=True,container=np.array)
                if Dpts+11 >= 400000:
                    self.connection.chunk_size = default_chunk
                conv_data = self.digital_pod_parser(raw_data)
                # parse out desired channels
                for connection,label in pod1_acquisitions:
                    channel_num = int(connection.split(' ')[-1])
                    data[connection] = conv_data[:,(7-channel_num)%8]
                    
            # read pod 2 channels if necessary     
            if len(pod2_acquisitions):     
                # use larger chunk size for faster large data reads
                [form,typ,Dpts,cnt,Dxinc,Dxor,Dxref,yinc,yor,yref] = self.connection.query_ascii_values(self.read_dig_parameters_string.format(2))
                if Dpts+11 >= 400000:
                    default_chunk = self.connection.chunk_size
                    self.connection.chunk_size = int(Dpts+11)
                raw_data = self.connection.query_binary_values(self.read_waveform_string,datatype='B',is_big_endian=True,container=np.array)
                if Dpts+11 >= 400000:
                    self.connection.chunk_size = default_chunk
                conv_data = self.digital_pod_parser(raw_data)
                # parse out desired channels
                for connection,label in pod2_acquisitions:
                    channel_num = int(connection.split(' ')[-1])
                    data[connection] = conv_data[:,(15-channel_num)%8]
                    
            if len(pod1_acquisitions) or len(pod2_acquisitions):
                # create the digital time array if needed
                # Note that digital traces always have fewer pts than analog
                data['Digital Time'] = np.arange(Dxref,Dxref+Dpts,1,dtype=np.float64)*Dxinc + Dxor
                    
            # read counters if necesary
            count_data = {}
            if len(counters):
                for connection,typ,pol in counters:
                    chan_num = int(connection.decode('UTF-8').split(' ')[-1])
                    count_data[connection] = float(self.connection.query(self.read_counter_string.format(pol,typ,chan_num)))                     
            
            # define the dtypes for the h5 arrays
            dtypes_analog = np.dtype({'names':['t','values'],'formats':[np.float64,np.float32]})  
            dtypes_digital = np.dtype({'names':['t','values'],'formats':[np.float64,np.uint8]})      
            
            # re-open lock on h5file to save data
            with h5py.File(self.h5_file,'r+') as hdf5_file:
                try:
                    measurements = hdf5_file['/data/traces']
                except:
                    # Group doesn't exist yet, create it
                    measurements = hdf5_file.create_group('/data/traces')
                # write out the data to the h5file
                for connection,label in analog_acquisitions:
                    values = np.empty(len(data[connection]),dtype=dtypes_analog)
                    values['t'] = data['Analog Time']
                    values['values'] = data[connection]
                    measurements.create_dataset(label, data=values, 
                                                **self.comp_settings)
                    # and save some timing info for reference to labscript time
                    measurements[label].attrs['trigger_time'] = trigger_time
                for connection,label in pod1_acquisitions:
                    values = np.empty(len(data[connection]),dtype=dtypes_digital)
                    values['t'] = data['Digital Time']
                    values['values'] = data[connection]
                    measurements.create_dataset(label, data=values, 
                                                **self.comp_settings)
                    # and save some timing info for reference to labscript time
                    measurements[label].attrs['trigger_time'] = trigger_time  
                for connection,label in pod2_acquisitions:
                    values = np.empty(len(data[connection]),dtype=dtypes_digital)
                    values['t'] = data['Digital Time']
                    values['values'] = data[connection]
                    measurements.create_dataset(label, data=values, 
                                                **self.comp_settings)
                    # and save some timing info for reference to labscript time
                    measurements[label].attrs['trigger_time'] = trigger_time   
            
                # Now read out the counters if they exist
                if len(counters):
                    try:
                        counts = hdf5_file['/data/'+self.device_name]
                    except:
                        counts = hdf5_file.create_group('/data/'+self.device_name)
                        
                    for connection,typ,pol in counters:
                        counts.attrs['{0:s}:{1:s}{2:s}'.format(connection,pol,typ)] = count_data[connection]
                        counts.attrs['trigger_time'] = trigger_time                                 
            
        return True
        
    def check_status(self):
        '''Periodically called by BLACS to check to status of the scope.'''
        # Scope don't say anything useful in the stb, 
        # using the event register instead
        esr = int(self.connection.query('*ESR?'))

        # if esr is non-zero, read out the error message and report
        if (esr & self.esr_mask) != 0:
            # read out errors from queue until response == 0
            err_string = ''
            while True:
                code, return_string = self.error_parser(self.connection.query(':SYST:ERR?'))
                if code != 0:
                    err_string += return_string
                else:
                    break
                
            raise LabscriptError('Keysight Scope VISA device {0:s} has Errors in Queue: \n{1:s}'.format(self.VISA_name,err_string)) 
        return self.convert_register(esr)
    

    # Added this from Tekcscope
    def abort(self):
        print('aborting!')
        self.scope.write('*RST')
        return True

    def abort_buffered(self):
        print('abort_buffered: ...')
        return self.abort()

    def abort_transition_to_buffered(self):
        print('abort_transition_to_buffered: ...')
        return self.abort()


