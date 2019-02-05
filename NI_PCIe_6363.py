#####################################################################
#                                                                   #
# /NI_PCIe_6363.py                                                  #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################
from __future__ import division, unicode_literals, print_function, absolute_import
from labscript_utils import PY2
if PY2:
    str = unicode

from labscript import LabscriptError
from labscript_devices import BLACS_tab, runviewer_parser
import labscript_devices.NIBoard as parent
from labscript_utils.numpy_dtype_workaround import dtype_workaround

import numpy as np
import labscript_utils.h5_lock, h5py
import labscript_utils.properties
from labscript_utils.connections import _ensure_str


class NI_PCIe_6363(parent.NIBoard):
    description = 'NI-PCIe-6363'
    n_analogs = 4
    n_digitals = 32
    n_analog_ins = 32
    digital_dtype = np.uint32


import time

from blacs.tab_base_classes import Worker, define_state
from blacs.tab_base_classes import MODE_MANUAL, MODE_TRANSITION_TO_BUFFERED, MODE_TRANSITION_TO_MANUAL, MODE_BUFFERED  
from blacs.device_base_class import DeviceTab

@BLACS_tab
class NI_PCIe_6363Tab(DeviceTab):
    def initialise_GUI(self):
        # Capabilities
        num = {'AO':4, 'DO':32, 'PFI':16}
        
        base_units = {'AO':'V'}
        base_min = {'AO':-10.0}
        base_max = {'AO':10.0}
        base_step = {'AO':0.1}
        base_decimals = {'AO':3}
        
        # Create the AO output objects
        ao_prop = {}
        for i in range(num['AO']):
            ao_prop['ao%d'%i] = {'base_unit':base_units['AO'],
                                 'min':base_min['AO'],
                                 'max':base_max['AO'],
                                 'step':base_step['AO'],
                                 'decimals':base_decimals['AO']
                                }
        
        do_prop = {}
        for i in range(num['DO']):
            do_prop['port0/line%d'%i] = {}
            
        pfi_prop = {}
        for i in range(num['PFI']):
            pfi_prop['PFI %d'%i] = {}
        
        
        # Create the output objects    
        self.create_analog_outputs(ao_prop)        
        # Create widgets for analog outputs only
        dds_widgets,ao_widgets,do_widgets = self.auto_create_widgets()
        
        # now create the digital output objects
        self.create_digital_outputs(do_prop)
        self.create_digital_outputs(pfi_prop)
        # manually create the digital output widgets so they are grouped separately
        do_widgets = self.create_digital_widgets(do_prop)
        pfi_widgets = self.create_digital_widgets(pfi_prop)
        
        def do_sort(channel):
            flag = channel.replace('port0/line','')
            flag = int(flag)
            return '%02d'%(flag)
            
        def pfi_sort(channel):
            flag = channel.replace('PFI ','')
            flag = int(flag)
            return '%02d'%(flag)
        
        # and auto place the widgets in the UI
        self.auto_place_widgets(("Analog Outputs",ao_widgets),("Digital Outputs",do_widgets,do_sort),("PFI Outputs",pfi_widgets,pfi_sort))
        
        # Store the Measurement and Automation Explorer (MAX) name
        self.MAX_name = str(self.settings['connection_table'].find_by_name(self.device_name).BLACS_connection)
        
        # Create and set the primary worker
        self.create_worker("main_worker",NiPCIe6363Worker,{'MAX_name':self.MAX_name, 'limits': [base_min['AO'],base_max['AO']], 'num':num})
        self.primary_worker = "main_worker"
        self.create_worker("wait_monitor_worker",NiPCIe6363WaitMonitorWorker,{'MAX_name':self.MAX_name})
        self.add_secondary_worker("wait_monitor_worker")
        self.create_worker("acquisition_worker",NiPCIe6363AcquisitionWorker,{'MAX_name':self.MAX_name})
        self.add_secondary_worker("acquisition_worker")

        # Set the capabilities of this device
        self.supports_remote_value_check(False)
        self.supports_smart_programming(False) 


class NiPCIe6363Worker(Worker):
    def init(self):
        exec('from PyDAQmx import Task, DAQmxGetSysNIDAQMajorVersion, DAQmxGetSysNIDAQMinorVersion, DAQmxGetSysNIDAQUpdateVersion, DAQmxResetDevice', globals())
        exec('from PyDAQmx.DAQmxConstants import *', globals())
        exec('from PyDAQmx.DAQmxTypes import *', globals())
        global pylab; import pylab
        global numpy; import numpy
        global h5py; import labscript_utils.h5_lock, h5py
        
        # check version of PyDAQmx
        major = uInt32()
        minor = uInt32()
        patch = uInt32()
        DAQmxGetSysNIDAQMajorVersion(major)
        DAQmxGetSysNIDAQMinorVersion(minor)
        DAQmxGetSysNIDAQUpdateVersion(patch)
        
        if major.value == 14 and minor.value < 2:
            version_exception_message = 'There is a known bug with buffered shots using NI DAQmx v14.0.0. This bug does not exist on v14.2.0. You are currently using v%d.%d.%d. Please ensure you upgrade to v14.2.0 or higher.'%(major.value, minor.value, patch.value)
            raise Exception(version_exception_message)
        
        # Create task
        self.ao_task = Task()
        self.ao_read = int32()
        self.ao_data = numpy.zeros((self.num['AO'],), dtype=numpy.float64)
        
        # Create DO task:
        self.do_task = Task()
        self.do_read = int32()
        self.do_data = numpy.zeros(self.num['DO']+self.num['PFI'],dtype=numpy.uint8)
        
        self.setup_static_channels()            
        
        #DAQmx Start Code        
        self.ao_task.StartTask() 
        self.do_task.StartTask()  
        
    def setup_static_channels(self):
        #setup AO channels
        for i in range(self.num['AO']): 
            self.ao_task.CreateAOVoltageChan(self.MAX_name+"/ao%d"%i,"",self.limits[0],self.limits[1],DAQmx_Val_Volts,None)
        
        #setup DO ports
        self.do_task.CreateDOChan(self.MAX_name+"/port0/line0:7","",DAQmx_Val_ChanForAllLines)
        self.do_task.CreateDOChan(self.MAX_name+"/port0/line8:15","",DAQmx_Val_ChanForAllLines)
        self.do_task.CreateDOChan(self.MAX_name+"/port0/line16:23","",DAQmx_Val_ChanForAllLines)
        self.do_task.CreateDOChan(self.MAX_name+"/port0/line24:31","",DAQmx_Val_ChanForAllLines)
        self.do_task.CreateDOChan(self.MAX_name+"/port1/line0:7","",DAQmx_Val_ChanForAllLines)
        self.do_task.CreateDOChan(self.MAX_name+"/port2/line0:7","",DAQmx_Val_ChanForAllLines)  
                
    def shutdown(self):        
        self.ao_task.StopTask()
        self.ao_task.ClearTask()
        self.do_task.StopTask()
        self.do_task.ClearTask()
        
    def program_manual(self,front_panel_values):
        for i in range(self.num['AO']):
            self.ao_data[i] = front_panel_values['ao%d'%i]
        self.ao_task.WriteAnalogF64(1,True,1,DAQmx_Val_GroupByChannel,self.ao_data,byref(self.ao_read),None)
        
        for i in range(self.num['DO']):
            self.do_data[i] = front_panel_values['port0/line%d'%i]
            
        for i in range(self.num['PFI']):
            self.do_data[i+self.num['DO']] = front_panel_values['PFI %d'%i]
        self.do_task.WriteDigitalLines(1,True,1,DAQmx_Val_GroupByChannel,self.do_data,byref(self.do_read),None)
     
        # TODO: return coerced/quantised values
        return {}
        
    def transition_to_buffered(self,device_name,h5file,initial_values,fresh):
        # Store the initial values in case we have to abort and restore them:
        self.initial_values = initial_values
            
        with h5py.File(h5file,'r') as hdf5_file:
            group = hdf5_file['devices/'][device_name]
            device_properties = labscript_utils.properties.get(hdf5_file, device_name, 'device_properties')
            connection_table_properties = labscript_utils.properties.get(hdf5_file, device_name, 'connection_table_properties')
            clock_terminal = connection_table_properties['clock_terminal']            
            h5_data = group.get('ANALOG_OUTS')
            if h5_data:
                self.buffered_using_analog = True
                ao_channels = device_properties['analog_out_channels']
                # We use all but the last sample (which is identical to the
                # second last sample) in order to ensure there is one more
                # clock tick than there are samples. The 6733 requires this
                # to determine that the task has completed.
                ao_data = pylab.array(h5_data,dtype=float64)[:-1,:]
            else:
                self.buffered_using_analog = False
                
            h5_data = group.get('DIGITAL_OUTS')
            if h5_data:
                self.buffered_using_digital = True
                do_channels = device_properties['digital_lines']
                do_bitfield = numpy.array(h5_data,dtype=numpy.uint32)
            else:
                self.buffered_using_digital = False
                
                
        
        final_values = {} 
        # We must do digital first, so as to make sure the manual mode task is stopped, or reprogrammed, by the time we setup the AO task
        # this is because the clock_terminal PFI must be freed!
        if self.buffered_using_digital:
            # Expand each bitfield int into self.num['DO']
            # (32) individual ones and zeros:
            do_write_data = numpy.zeros((do_bitfield.shape[0],self.num['DO']),dtype=numpy.uint8)
            for i in range(self.num['DO']):
                do_write_data[:,i] = (do_bitfield & (1 << i)) >> i
                
            self.do_task.StopTask()
            self.do_task.ClearTask()
            self.do_task = Task()
            self.do_read = int32()
    
            self.do_task.CreateDOChan(do_channels,"",DAQmx_Val_ChanPerLine)
            self.do_task.CfgSampClkTiming(clock_terminal,1000000,DAQmx_Val_Rising,DAQmx_Val_FiniteSamps,do_bitfield.shape[0])
            self.do_task.WriteDigitalLines(do_bitfield.shape[0],False,10.0,DAQmx_Val_GroupByScanNumber,do_write_data,self.do_read,None)
            self.do_task.StartTask()
            
            for i in range(self.num['DO']):
                final_values['port0/line%d'%i] = do_write_data[-1,i]
        else:
            # We still have to stop the task to make the 
            # clock flag available for buffered analog output, or the wait monitor:
            self.do_task.StopTask()
            self.do_task.ClearTask()
            
        if self.buffered_using_analog:
            self.ao_task.StopTask()
            self.ao_task.ClearTask()
            self.ao_task = Task()
            ao_read = int32()

            self.ao_task.CreateAOVoltageChan(ao_channels,"",-10.0,10.0,DAQmx_Val_Volts,None)
            self.ao_task.CfgSampClkTiming(clock_terminal,1000000,DAQmx_Val_Rising,DAQmx_Val_FiniteSamps, ao_data.shape[0])
            
            self.ao_task.WriteAnalogF64(ao_data.shape[0],False,10.0,DAQmx_Val_GroupByScanNumber, ao_data,ao_read,None)
            self.ao_task.StartTask()   
            
            # Final values here are a dictionary of values, keyed by channel:
            channel_list = [channel.split('/')[1] for channel in ao_channels.split(', ')]
            for channel, value in zip(channel_list, ao_data[-1,:]):
                final_values[channel] = value
        else:
            # we should probabaly still stop the task (this makes it easier to setup the task later)
            self.ao_task.StopTask()
            self.ao_task.ClearTask()
                
       
            
        return final_values
        
    def transition_to_manual(self,abort=False):
        # if aborting, don't call StopTask since this throws an
        # error if the task hasn't actually finished!
        if self.buffered_using_analog:
            if not abort:
                self.ao_task.StopTask()
            self.ao_task.ClearTask()
        if self.buffered_using_digital:
            if not abort:
                self.do_task.StopTask()
            self.do_task.ClearTask()
                
        self.ao_task = Task()
        self.do_task = Task()
        self.setup_static_channels()
        self.ao_task.StartTask()
        self.do_task.StartTask()
        if abort:
            # Reprogram the initial states:
            self.program_manual(self.initial_values)
            
        return True
        
    def abort_transition_to_buffered(self):
        # TODO: untested
        return self.transition_to_manual(True)
        
    def abort_buffered(self):
        # TODO: untested
        return self.transition_to_manual(True)    

        
class NiPCIe6363AcquisitionWorker(Worker):
    def init(self):
        #exec 'import traceback' in globals()
        exec('from PyDAQmx import Task', globals())
        exec('from PyDAQmx.DAQmxConstants import *', globals())
        exec('from PyDAQmx.DAQmxTypes import *', globals())
        global h5py; import labscript_utils.h5_lock, h5py
        global numpy; import numpy
        global threading; import threading
        global zprocess; import zprocess
        global logging; import logging
        global time; import time
        
        self.task_running = False
        self.daqlock = threading.Condition()
        # Channel details
        self.channels = []
        self.rate = 1000.
        self.samples_per_channel = 1000
        self.ai_start_delay = 25e-9
        self.h5_file = ""
        self.buffered_channels = []
        self.buffered_rate = 0
        self.buffered = False
        self.buffered_data = None
        self.buffered_data_list = []
        
        self.task = None
        self.abort = False
        
        # And event for knowing when the wait durations are known, so that we may use them
        # to chunk up acquisition data:
        self.wait_durations_analysed = zprocess.Event('wait_durations_analysed')
        
        self.daqmx_read_thread = threading.Thread(target=self.daqmx_read)
        self.daqmx_read_thread.daemon = True
        self.daqmx_read_thread.start()

    def shutdown(self):
        if self.task_running:
            self.stop_task()
        
    def daqmx_read(self):
        logger = logging.getLogger('BLACS.%s_%s.acquisition.daqmxread'%(self.device_name,self.worker_name))
        logger.info('Starting')
        #first_read = True
        try:
            while True:
                with self.daqlock:
                    logger.debug('Got daqlock')
                    while not self.task_running:
                        logger.debug('Task isn\'t running. Releasing daqlock and waiting to reacquire it.')
                        self.daqlock.wait()
                    #logger.debug('Reading data from analogue inputs')
                    if self.buffered:
                        chnl_list = self.buffered_channels
                    else:
                        chnl_list = self.channels
                    try:
                        error = "Task did not return an error, but it should have"
                        acquisition_timeout = 5
                        error = self.task.ReadAnalogF64(self.samples_per_channel,acquisition_timeout,DAQmx_Val_GroupByChannel,self.ai_data,self.samples_per_channel*len(chnl_list),byref(self.ai_read),None)
                        #logger.debug('Reading complete')
                        if error is not None and error != 0:
                            if error < 0:
                                raise Exception(error)
                            if error > 0:
                                logger.warning(error)
                    except Exception as e:
                        logger.exception('acquisition error')
                        if self.abort:
                            # If an abort is in progress, then we expect an exception here. Don't raise it.
                            logger.debug('ignoring error since an abort is in progress.')
                            # Ensure the next iteration of this while loop
                            # doesn't happen until the task is restarted.
                            # The thread calling self.stop_task() is
                            # also setting self.task_running = False
                            # right about now, but we don't want to rely
                            # on it doing so in time. Doing it here too
                            # avoids a race condition.
                            self.task_running = False
                            continue
                        else:
                            # Error was likely a timeout error...some other device might be bing slow 
                            # transitioning to buffered, so we haven't got our start trigger yet. 
                            # Keep trying until task_running is False:
                            continue
                # send the data to the queue
                if self.buffered:
                    # rearrange ai_data into correct form
                    data = numpy.copy(self.ai_data)
                    self.buffered_data_list.append(data)
                    
                    #if len(chnl_list) > 1:
                    #    data.shape = (len(chnl_list),self.ai_read.value)              
                    #    data = data.transpose()
                    #self.buffered_data = numpy.append(self.buffered_data,data,axis=0)
                else:
                    pass
                    # Todo: replace this with zmq pub plus a broker somewhere so things can subscribe to channels
                    # and get their data without caring what process it came from. For the sake of speed, this
                    # should use the numpy buffer interface and raw zmq messages, and not the existing event system
                    # that zprocess has.
                    # self.result_queue.put([self.t0,self.rate,self.ai_read.value,len(self.channels),self.ai_data])
                    # self.t0 = self.t0 + self.samples_per_channel/self.rate
        except:
            message = traceback.format_exc()
            logger.error('An exception happened:\n %s'%message)
            #self.to_parent.put(['error', message])
            # TODO: Tell the GUI process that this has a problem some how (status check?)
            
    def setup_task(self):
        self.logger.debug('setup_task')
        #DAQmx Configure Code
        with self.daqlock:
            self.logger.debug('setup_task got daqlock')
            if self.task:
                self.task.ClearTask()##
            if self.buffered:
                chnl_list = self.buffered_channels
                rate = self.buffered_rate
            else:
                chnl_list = self.channels
                rate = self.rate
                
            if len(chnl_list) < 1:
                return
                
            if rate < 1000:
                self.samples_per_channel = int(rate)
            else:
                self.samples_per_channel = 1000
            try:
                self.task = Task()
            except Exception as e:
                self.logger.error(str(e))
            self.ai_read = int32()
            self.ai_data = numpy.zeros((self.samples_per_channel*len(chnl_list),), dtype=numpy.float64)   
            
            for chnl in chnl_list:
                self.task.CreateAIVoltageChan(chnl,"",DAQmx_Val_RSE,-10.0,10.0,DAQmx_Val_Volts,None)
                
            self.task.CfgSampClkTiming("",rate,DAQmx_Val_Rising,DAQmx_Val_ContSamps,1000)
                    
            if self.buffered:
                #set up start on digital trigger
                self.task.CfgDigEdgeStartTrig(self.clock_terminal,DAQmx_Val_Rising)
            
            #DAQmx Start Code
            self.task.StartTask()
            # TODO: Need to do something about the time for buffered acquisition. Should be related to when it starts (approx)
            # How do we detect that?
            self.t0 = time.time() - time.timezone
            self.task_running = True
            self.daqlock.notify()
        self.logger.debug('finished setup_task')
        
    def stop_task(self):
        self.logger.debug('stop_task')
        with self.daqlock:
            self.logger.debug('stop_task got daqlock')
            if self.task_running:
                self.task_running = False
                self.task.StopTask()
                self.task.ClearTask()
            self.daqlock.notify()
        self.logger.debug('finished stop_task')
        
    def transition_to_buffered(self,device_name,h5file,initial_values,fresh):
        # TODO: Do this line better!
        self.device_name = device_name
        
        self.logger.debug('transition_to_buffered')
        # stop current task
        self.stop_task()
        
        self.buffered_data_list = []
        
        # Save h5file path (for storing data later!)
        self.h5_file = h5file
        # read channels, acquisition rate, etc from H5 file
        h5_chnls = []
        with h5py.File(h5file,'r') as hdf5_file:
            group =  hdf5_file['/devices/'+device_name]
            device_properties = labscript_utils.properties.get(hdf5_file, device_name, 'device_properties')
            connection_table_properties = labscript_utils.properties.get(hdf5_file, device_name, 'connection_table_properties')
            self.clock_terminal = connection_table_properties['clock_terminal']            
            if 'analog_in_channels' in device_properties:
                h5_chnls = device_properties['analog_in_channels'].split(', ')
                self.buffered_rate = device_properties['acquisition_rate']
            else:
               self.logger.debug("no input channels")
        # combine static channels with h5 channels (using a set to avoid duplicates)
        self.buffered_channels = set(h5_chnls)
        self.buffered_channels.update(self.channels)
        # Now make it a sorted list:
        self.buffered_channels = sorted(list(self.buffered_channels))
        
        # setup task (rate should be from h5 file)
        # Possibly should detect and lower rate if too high, as h5 file doesn't know about other acquisition channels?
        
        if self.buffered_rate <= 0:
            self.buffered_rate = self.rate
        
        self.buffered = True
        if len(self.buffered_channels) == 1:
            self.buffered_data = numpy.zeros((1,),dtype=numpy.float64)
        else:
            self.buffered_data = numpy.zeros((1,len(self.buffered_channels)),dtype=numpy.float64)
        
        self.setup_task()   

        return {}
    
    def transition_to_manual(self,abort=False):    
        self.logger.debug('transition_to_static')
        # Stop acquisition (this should really be done on a digital edge, but that is for later! Maybe use a Counter)
        # Set the abort flag so that the acquisition thread knows to expect an exception in the case of an abort:
        #
        # TODO: This is probably bad because it shortly get's overwritten to False
        # However whether it has an effect depends on whether daqmx_read thread holds the daqlock 
        # when self.stop_task() is called
        self.abort = abort 
        self.stop_task()
        # Reset the abort flag so that unexpected exceptions are still raised:        
        self.abort = False
        self.logger.info('transitioning to static, task stopped')
        # save the data acquired to the h5 file
        if not abort:
            with h5py.File(self.h5_file,'a') as hdf5_file:
                data_group = hdf5_file['data']
                data_group.create_group(self.device_name)

            dtypes = [(chan.split('/')[-1],numpy.float32) for chan in sorted(self.buffered_channels)]

            start_time = time.time()
            if self.buffered_data_list:
                self.buffered_data = numpy.zeros(len(self.buffered_data_list)*1000,dtype=dtype_workaround(dtypes))
                for i, data in enumerate(self.buffered_data_list):
                    data.shape = (len(self.buffered_channels),self.ai_read.value)              
                    for j, (chan, dtype) in enumerate(dtypes):
                        self.buffered_data[chan][i*1000:(i*1000)+1000] = data[j,:]
                    if i % 100 == 0:
                        self.logger.debug( str(i/100) + " time: "+str(time.time()-start_time))
                self.extract_measurements(self.device_name)
                self.logger.info('data written, time taken: %ss' % str(time.time()-start_time))
            
            self.buffered_data = None
            self.buffered_data_list = []
            
            # Send data to callback functions as requested (in one big chunk!)
            #self.result_queue.put([self.t0,self.rate,self.ai_read,len(self.channels),self.ai_data])
        
        # return to previous acquisition mode
        self.buffered = False
        self.setup_task()
        
        return True
        
    def extract_measurements(self, device_name):
        self.logger.debug('extract_measurements')
        with h5py.File(self.h5_file,'a') as hdf5_file:
            waits_in_use = len(hdf5_file['waits']) > 0
        if waits_in_use:
            # There were waits in this shot. We need to wait until the other process has
            # determined their durations before we proceed:
            self.wait_durations_analysed.wait(self.h5_file)
            
        with h5py.File(self.h5_file,'a') as hdf5_file:
            if waits_in_use:
                # get the wait start times and durations
                waits = hdf5_file['/data/waits']
                wait_times = waits['time']
                wait_durations = waits['duration']
            try:
                acquisitions = hdf5_file['/devices/'+device_name+'/ACQUISITIONS']
            except:
                # No acquisitions!
                return
            try:
                measurements = hdf5_file['/data/traces']
            except:
                # Group doesn't exist yet, create it:
                measurements = hdf5_file.create_group('/data/traces')
            for connection,label,start_time,end_time,wait_label,scale_factor,units in acquisitions:
                connection = _ensure_str(connection)
                label = _ensure_str(label)
                wait_label = _ensure_str(wait_label)
                if waits_in_use:
                    # add durations from all waits that start prior to start_time of acquisition
                    start_time += wait_durations[(wait_times < start_time)].sum()
                    # compare wait times to end_time to allow for waits during an acquisition
                    end_time += wait_durations[(wait_times < end_time)].sum()
                start_index = int(numpy.ceil(self.buffered_rate*(start_time-self.ai_start_delay)))
                end_index = int(numpy.floor(self.buffered_rate*(end_time-self.ai_start_delay)))
                # numpy.ceil does what we want above, but float errors can miss the equality
                if self.ai_start_delay + (start_index-1)/self.buffered_rate - start_time > -2e-16:
                    start_index -= 1
                # We actually want numpy.floor(x) to yield the largest integer < x (not <=) 
                if end_time - self.ai_start_delay - end_index/self.buffered_rate < 2e-16:
                    end_index -= 1
                acquisition_start_time = self.ai_start_delay + start_index/self.buffered_rate
                acquisition_end_time = self.ai_start_delay + end_index/self.buffered_rate
                times = numpy.linspace(acquisition_start_time, acquisition_end_time, 
                                       end_index-start_index+1,
                                       endpoint=True)
                values = self.buffered_data[connection][start_index:end_index+1]
                dtypes = [('t', numpy.float64),('values', numpy.float32)]
                data = numpy.empty(len(values),dtype=dtype_workaround(dtypes))
                data['t'] = times
                data['values'] = values
                measurements.create_dataset(label, data=data)
            
    def abort_buffered(self):
        #TODO: test this
        return self.transition_to_manual(True)
        
    def abort_transition_to_buffered(self):
        #TODO: test this
        return self.transition_to_manual(True)   
    
    def program_manual(self,values):
        return {}
    
class NiPCIe6363WaitMonitorWorker(Worker):
    def init(self):
        exec('import ctypes', globals())
        exec('from PyDAQmx import Task', globals())
        exec('from PyDAQmx.DAQmxConstants import *', globals())
        exec('from PyDAQmx.DAQmxTypes import *', globals())
        global h5py; import labscript_utils.h5_lock, h5py
        global numpy; import numpy        
        global threading; import threading
        global zprocess; import zprocess
        global logging; import logging
        global time; import time
    
        self.task_running = False
        self.daqlock = threading.Lock() # not sure if needed, access should be serialised already
        self.h5_file = None
        self.task = None
        self.abort = False
        self.all_waits_finished = zprocess.Event('all_waits_finished',type='post')
        self.wait_durations_analysed = zprocess.Event('wait_durations_analysed',type='post')
    
    def shutdown(self):
        self.logger.info('Shutdown requested, stopping task')
        if self.task_running:
            self.stop_task()    
    
    #def read_one_half_period(self, timeout, readarray = numpy.empty(1)):
    def read_one_half_period(self, timeout): 
        readarray = numpy.empty(1)
        try:
            with self.daqlock:
                self.acquisition_task.ReadCounterF64(1, timeout, readarray, len(readarray), ctypes.c_long(1), None)
                self.half_periods.append(readarray[0])
            return readarray[0]
        except Exception:
            if self.abort:
                raise
            # otherwise, it's a timeout:
            return None
    
    def wait_for_edge(self, timeout=None):
        if timeout is None:
            while True:
                half_period = self.read_one_half_period(1)
                if half_period is not None:
                    return half_period
        else:
            return self.read_one_half_period(timeout)
                
    def daqmx_read(self):
        logger = logging.getLogger('BLACS.%s_%s.read_thread'%(self.device_name, self.worker_name))
        logger.info('Starting')
        with self.kill_lock:
            try:
                # Wait for the end of the first pulse indicating the start of the experiment:
                current_time = pulse_width = self.wait_for_edge()
                # alright, we're now a short way into the experiment.
                for wait in self.wait_table:
                    # How long until this wait should time out?
                    timeout = wait['time'] + wait['timeout'] - current_time
                    timeout = max(timeout, 0) # ensure non-negative
                    # Wait that long for the next pulse:
                    half_period = self.wait_for_edge(timeout)
                    # Did the wait finish of its own accord?
                    if half_period is not None:
                        # It did, we are now at the end of that wait:
                        logger.info('Wait completed')
                        current_time = wait['time']
                        # Wait for the end of the pulse:
                        current_time += self.wait_for_edge()
                    else:
                        # It timed out. Better trigger the clock to resume!
                        logger.info('Wait timed out; retriggering clock with {:.3e} s pulse ({} edge)'.format(pulse_width, self.timeout_trigger_type))
                        self.send_resume_trigger(pulse_width)
                        # Wait for it to respond to that:
                        logger.info('Waiting for edge on WaitMonitor')
                        self.wait_for_edge()
                        # Alright, *now* we're at the end of the wait.
                        logger.info('Wait completed')
                        current_time = wait['time']
                        # And wait for the end of the pulse:
                        current_time += self.wait_for_edge()

                # Inform any interested parties that waits have all finished:
                logger.info('All waits finished')
                self.all_waits_finished.post(self.h5_file)
            except Exception:
                if self.abort:
                    return
                else:
                    raise
    
    def send_resume_trigger(self, pulse_width):
        written = int32()
        if self.timeout_trigger_type == 'rising':
            trigger_value = 1
            rearm_value = 0
        elif self.timeout_trigger_type == 'falling':
            trigger_value = 0
            rearm_value = 1
        else:
            raise ValueError('timeout_trigger_type of {}_{} must be either "rising" or "falling".'.format(self.device_name, self.worker_name))
        # Triggering edge:
        self.timeout_task.WriteDigitalLines(1, True, 1, DAQmx_Val_GroupByChannel, np.array([trigger_value], dtype=np.uint8), byref(written), None)
        assert written.value == 1
        # Wait however long we observed the first pulse of the experiment to be:
        time.sleep(pulse_width)
        # Rearm trigger
        self.timeout_task.WriteDigitalLines(1, True, 1, DAQmx_Val_GroupByChannel, np.array([rearm_value], dtype=np.uint8), byref(written), None)
        assert written.value == 1
        
    def stop_task(self):
        self.logger.debug('stop_task')
        with self.daqlock:
            self.logger.debug('stop_task got daqlock')
            if self.task_running:
                self.task_running = False
                self.acquisition_task.StopTask()
                self.acquisition_task.ClearTask()
                self.timeout_task.StopTask()
                self.timeout_task.ClearTask()
        self.logger.debug('finished stop_task')
        
    def transition_to_buffered(self,device_name,h5file,initial_values,fresh):
        self.logger.debug('transition_to_buffered')
        # Save h5file path (for storing data later!)
        self.h5_file = h5file
        self.is_wait_monitor_device = False # Will be set to true in a moment if necessary
        self.logger.debug('setup_task')
        with h5py.File(h5file, 'r') as hdf5_file:
            dataset = hdf5_file['waits']
            if len(dataset) == 0:
                # There are no waits. Do nothing.
                self.logger.debug('There are no waits, not transitioning to buffered')
                self.waits_in_use = False
                self.wait_table = numpy.zeros((0,))
                return {}
            self.waits_in_use = True
            acquisition_device = dataset.attrs['wait_monitor_acquisition_device']
            acquisition_connection = dataset.attrs['wait_monitor_acquisition_connection']
            timeout_device = dataset.attrs['wait_monitor_timeout_device']
            timeout_connection = dataset.attrs['wait_monitor_timeout_connection']
            try:
                self.timeout_trigger_type = dataset.attrs['wait_monitor_timeout_trigger_type']
            except KeyError:
                self.timeout_trigger_type = 'rising'
            self.wait_table = dataset[:]
        # Only do anything if we are in fact the wait_monitor device:
        if timeout_device == device_name or acquisition_device == device_name:
            if not timeout_device == device_name and acquisition_device == device_name:
                raise NotImplementedError("ni-PCIe-6363 worker must be both the wait monitor timeout device and acquisition device." +
                                          "Being only one could be implemented if there's a need for it, but it isn't at the moment")
            
            self.is_wait_monitor_device = True
            # The counter acquisition task:
            self.acquisition_task = Task()
            acquisition_chan = '/'.join([self.MAX_name,acquisition_connection])
            self.acquisition_task.CreateCISemiPeriodChan(acquisition_chan, '', 100e-9, 200, DAQmx_Val_Seconds, "")    
            self.acquisition_task.CfgImplicitTiming(DAQmx_Val_ContSamps, 1000)
            self.acquisition_task.StartTask()
            # The timeout task:
            self.timeout_task = Task()
            timeout_chan = '/'.join([self.MAX_name,timeout_connection])
            self.timeout_task.CreateDOChan(timeout_chan,"",DAQmx_Val_ChanForAllLines)
            # Ensure timeout trigger is armed
            if self.timeout_trigger_type == 'falling':
                written = int32()
                self.timeout_task.WriteDigitalLines(1, True, 1, DAQmx_Val_GroupByChannel, np.array([1], dtype=np.uint8), byref(written), None)
                assert written.value == 1
            self.task_running = True
                
            # An array to store the results of counter acquisition:
            self.half_periods = []
            self.read_thread = threading.Thread(target=self.daqmx_read)
            # Not a daemon thread, as it implements wait timeouts - we need it to stay alive if other things die.
            self.read_thread.start()
            self.logger.debug('finished transition to buffered')
            
        return {}
    
    def transition_to_manual(self,abort=False):
        self.logger.debug('transition_to_static')
        self.abort = abort
        self.stop_task()
        # Reset the abort flag so that unexpected exceptions are still raised:        
        self.abort = False
        self.logger.info('transitioning to static, task stopped')
        # save the data acquired to the h5 file
        if not abort:
            if self.is_wait_monitor_device and self.waits_in_use:
                # Let's work out how long the waits were. The absolute times of each edge on the wait
                # monitor were:
                edge_times = numpy.cumsum(self.half_periods)
                # Now there was also a rising edge at t=0 that we didn't measure:
                edge_times = numpy.insert(edge_times,0,0)
                # Ok, and the even-indexed ones of these were rising edges.
                rising_edge_times = edge_times[::2]
                # Now what were the times between rising edges?
                periods = numpy.diff(rising_edge_times)
                # How does this compare to how long we expected there to be between the start
                # of the experiment and the first wait, and then between each pair of waits?
                # The difference will give us the waits' durations.
                resume_times = self.wait_table['time']
                # Again, include the start of the experiment, t=0:
                resume_times =  numpy.insert(resume_times,0,0)
                run_periods = numpy.diff(resume_times)
                wait_durations = periods - run_periods
                waits_timed_out = wait_durations > self.wait_table['timeout']
            with h5py.File(self.h5_file,'a') as hdf5_file:
                # Work out how long the waits were, save em, post an event saying so 
                dtypes = [('label','a256'),('time',float),('timeout',float),('duration',float),('timed_out',bool)]
                data = numpy.empty(len(self.wait_table), dtype=dtype_workaround(dtypes))
                if self.is_wait_monitor_device and self.waits_in_use:
                    data['label'] = self.wait_table['label']
                    data['time'] = self.wait_table['time']
                    data['timeout'] = self.wait_table['timeout']
                    data['duration'] = wait_durations
                    data['timed_out'] = waits_timed_out
                if self.is_wait_monitor_device:
                    hdf5_file.create_dataset('/data/waits', data=data)
            if self.is_wait_monitor_device:
                self.wait_durations_analysed.post(self.h5_file)
        
        return True
    
    def abort_buffered(self):
        #TODO: test this
        return self.transition_to_manual(True)
        
    def abort_transition_to_buffered(self):
        #TODO: test this
        return self.transition_to_manual(True)   
    
    def program_manual(self,values):
        return {}

 
    
@runviewer_parser
class RunviewerClass(parent.RunviewerClass):
    num_digitals = 32
    
