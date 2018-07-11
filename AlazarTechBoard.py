# A labscript device class for data acquisition boards made by Alazar Technologies Inc (ATS)
# Hacked up from NIboard.py by LDT 2017-01-26
#
# Copyright (c) Monash University 2017
from __future__ import division
# from __future__ import  unicode_literals # seems oddly problematic
from __future__ import print_function
import ctypes
import numpy as np
import signal
import sys
import time

# Install atsapi.py into site-packages for this to work
# or keep in local directory.
import atsapi as ats

# Talk mv to card set range
# All ATS ranges given below,
# but have commented out the ones that don't work with our ATS9462
atsRanges={
#40: ats.INPUT_RANGE_PM_40_MV,
# 50: ats.INPUT_RANGE_PM_50_MV,
# 80: ats.INPUT_RANGE_PM_80_MV,
#100: ats.INPUT_RANGE_PM_100_MV,
200: ats.INPUT_RANGE_PM_200_MV,
400: ats.INPUT_RANGE_PM_400_MV,
#500: ats.INPUT_RANGE_PM_500_MV,
800: ats.INPUT_RANGE_PM_800_MV,
#1000: ats.INPUT_RANGE_PM_1_V,
2000: ats.INPUT_RANGE_PM_2_V,
4000: ats.INPUT_RANGE_PM_4_V,
#5000: ats.INPUT_RANGE_PM_5_V,
#8000: ats.INPUT_RANGE_PM_8_V,
#10000: ats.INPUT_RANGE_PM_10_V, 
#20000: ats.INPUT_RANGE_PM_20_V,
#40000: ats.INPUT_RANGE_PM_40_V, 
#16000: ats.INPUT_RANGE_PM_16_V,
#1250: ats.INPUT_RANGE_PM_1_V_25, 
#2500: ats.INPUT_RANGE_PM_2_V_5,  
#125: ats.INPUT_RANGE_PM_125_MV, 
#250: ats.INPUT_RANGE_PM_250_MV
}


atsSampleRates={
1000:      ats.SAMPLE_RATE_1KSPS,
2000:      ats.SAMPLE_RATE_2KSPS,
5000:      ats.SAMPLE_RATE_5KSPS,
10000:     ats.SAMPLE_RATE_10KSPS,
20000:     ats.SAMPLE_RATE_20KSPS,
50000:     ats.SAMPLE_RATE_50KSPS,
100000:    ats.SAMPLE_RATE_100KSPS,
200000:    ats.SAMPLE_RATE_200KSPS,
500000:    ats.SAMPLE_RATE_500KSPS,
1000000:   ats.SAMPLE_RATE_1MSPS,
2000000:   ats.SAMPLE_RATE_2MSPS,
5000000:   ats.SAMPLE_RATE_5MSPS,
10000000:  ats.SAMPLE_RATE_10MSPS,
20000000:  ats.SAMPLE_RATE_20MSPS,
25000000:  ats.SAMPLE_RATE_25MSPS,
50000000:  ats.SAMPLE_RATE_50MSPS,
100000000: ats.SAMPLE_RATE_100MSPS,
125000000: ats.SAMPLE_RATE_125MSPS,
160000000: ats.SAMPLE_RATE_160MSPS,
180000000: ats.SAMPLE_RATE_180MSPS
}


if __name__ != "__main__":
    import numpy as np #Done above
    from labscript_devices import labscript_device
    from labscript import Device, AnalogIn, bitfield, config, LabscriptError, set_passed_properties
    import labscript_utils.h5_lock, h5py  
    import labscript_utils.properties
    import labscript_utils.shared_drive as shared_drive
    import atsapi as ats

    class AlazarTechBoard(Device):
        allowed_children = [AnalogIn]
        description = 'Generic_Alazar_Technologies_capture_board'

    # Many properties not supported. Examples include:
    # AlazarSetExternalClockLevel, SetDataFormat
    # Anything to do with board memory
    # Anything "for scanning"
        @set_passed_properties(property_names = {
            "device_properties":["ats_system_id", "ats_board_id",
                             "requested_acquisition_rate", "acquisition_duration",
                             "clock_source_id", "sample_rate_id_or_value", "clock_edge_id", "decimation",
                             "trig_operation",
                             "trig_engine_id1", "trig_source_id1", "trig_slope_id1",  "trig_level_id1",
                             "trig_engine_id2", "trig_source_id2", "trig_slope_id2", "trig_level_id2",
                             "exttrig_coupling_id", "exttrig_range_id",
                             "trig_delay_samples", "trig_timeout_10usecs", "input_range",
                             "channels",
                             "chA_coupling_id", "chA_input_range", "chA_impedance_id", "chA_bw_limit",
                             "chB_coupling_id", "chB_input_range", "chB_impedance_id", "chB_bw_limit"
                             ]
        })
        def __init__(self, name, server,
                     ats_system_id=1, ats_board_id=1,
                     requested_acquisition_rate=0, # No default for this, must be calculated and set!
                     acquisition_duration    = 1,  # In seconds. This should be set up by .acquire calls, but too bad for now. 
                     clock_source_id         = ats  .INTERNAL_CLOCK,
                     sample_rate_id          = ats.SAMPLE_RATE_180MSPS,
                     clock_edge_id           = ats.CLOCK_EDGE_RISING,
                     decimation              = 0, 
                     trig_operation          = ats.TRIG_ENGINE_OP_J,
                     trig_engine_id1         = ats.TRIG_ENGINE_J,
                     trig_source_id1         = ats.TRIG_EXTERNAL,
                     trig_slope_id1          = ats.TRIGGER_SLOPE_POSITIVE,
                     trig_level_id1          = 128, # 0 mV
                     trig_engine_id2         = ats.TRIG_ENGINE_K,
                     trig_source_id2         = ats.TRIG_DISABLE,
                     trig_slope_id2          = ats.TRIGGER_SLOPE_POSITIVE,
                     trig_level_id2          = 128, # 0 mV
                     exttrig_coupling_id     = ats.DC_COUPLING,
                     exttrig_range_id        = ats.ETR_5V,
                     trig_delay_samples      = 0,
                     trig_timeout_10usecs    = 0,
                     channels                = (ats.CHANNEL_A | ats.CHANNEL_B), 
                     chA_coupling_id         = ats.AC_COUPLING,
                     chA_input_range         = 4000,
                     chA_impedance_id        = ats.IMPEDANCE_1M_OHM,
                     chA_bw_limit            = 0,
                     chB_coupling_id         = ats.AC_COUPLING,
                     chB_input_range         = 4000,
                     chB_impedance_id        = ats.IMPEDANCE_1M_OHM,
                     chB_bw_limit            = 0):
            Device.__init__(self, name, None, None)
            self.name = name
            self.BLACS_connection = server  # This line makes BLACS think the device is connected to something
            
        def add_device(self, output):
            # TODO: check there are no duplicates, check that connection
            # string is formatted correctly.
            Device.add_device(self, output)

        # Has no children for now so hopefully does nothing
        def generate_code(self, hdf5_file):
            Device.generate_code(self, hdf5_file)
            inputs = {}
            for device in self.child_devices:
                if isinstance(device, AnalogIn):
                    inputs[device.connection] = device
                else:
                    raise Exception('Got unexpected device.')
            input_connections = inputs.keys()
            input_connections.sort()
            input_attrs = []
            acquisitions = []
            for connection in input_connections:
                input_attrs.append(self.name+'/'+connection)
                for acq in inputs[connection].acquisitions:
                    acquisitions.append((connection,acq['label'],acq['start_time'],acq['end_time'],acq['wait_label'],acq['scale_factor'],acq['units']))
            acquisitions_table_dtypes = [('connection','a256'), ('label','a256'), ('start',float),
                                         ('stop',float), ('wait label','a256'),('scale factor',float), ('units','a256')]
            acquisition_table= np.empty(len(acquisitions), dtype=acquisitions_table_dtypes)
            for i, acq in enumerate(acquisitions):
                acquisition_table[i] = acq
                grp = self.init_device_group(hdf5_file)
            if len(acquisition_table): # Table must be non empty
                grp.create_dataset('ACQUISITIONS',compression=config.compression,data=acquisition_table)
                self.set_property('analog_in_channels', ', '.join(input_attrs), location='device_properties')

    from labscript_devices import BLACS_tab, BLACS_worker
    from blacs.tab_base_classes import Worker, define_state
    from blacs.tab_base_classes import MODE_MANUAL, MODE_TRANSITION_TO_BUFFERED, MODE_TRANSITION_TO_MANUAL, MODE_BUFFERED 
    from blacs.device_base_class import DeviceTab
    import os
    import copy

    # A BLACS tab for a purely remote device which does not need configuration of parameters in BLACS
    @BLACS_tab
    class GuilessTab(DeviceTab):
        def initialise_GUI(self):
            pass

        def get_save_data(self):
            return {}

        def restore_save_data(self, save_data):
            pass

        def initialise_workers(self):
            # Create and set the primary worker
            self.create_worker("main_worker",GuilessWorker,{})
            self.primary_worker = "main_worker"

# As a substitute for real documentation, here's an outline for what the Alazar worker does. 
# This should be sphinx'ed or whatever.
# The main thread in init() kicks off a long-lived (as long as the main thread) "acquisition thread", running acquisition_loop()
# The acquisition thread is an infinite loop, at the top of which it immediately waits on the acquisition_queue.
# This is where we are when BLACS is 'idle'.
# *** How it SHOULD operate:
# At transition_to_buffered, the main thread sets up the card params and the acquisition buffers, and just before returning sends a 'start' down the queue to the acq thread.
# The acquisition thread proceeds to the blocking waitNextAsyncBufferComplete() call, which waits for the first buffer to be filled.
# All being well, the buffers are filled in sequence and the acquisition thread set the acqusition_done flag, 
# and continues to the top of its loop, waiting for the next 'start' command down the queue.
# Eventually it's transition_to_manual time, and starts by checking the 'acquisition_done' flag via wait_acquisition_complete(), with a short timeout of 2 seconds.
# If the acquisition is actually done, the flag is cleared, and it proceeds to write the buffers into the h5 file and free them, returning.
# We are back in BLACS-idle, with the acquisition thread waiting for a 'start' command again.
# *** What happens if the trigger isn't sent
# In the acquisition thread, the call to waitNextAsyncBufferComplete() eventually times out, generating an exception.
# This timout is set to 60s (and should be set to experiment_duration), but has no way of knowing when in the experiment the acquisition started, so it will likely
# not time out until well after transition_to_manual is called.
# Transition_to_manual gets called, finds the acquisition_done flag is low, times out quickly (2s) waiting for this, and raises an exception 'Waiting for acquisition to complete timed out'
# This exception kills the main thread, which should lead to the death of the acquisition thread too, but it is still blocking.
# Eventually the acquisition thread would time out and die with an AlazarException (code ApiWaitTimeout). But rather than waiting for this, we call abortAsyncRead() from the main thread.
# This forces the waitNextAsyncBufferComplete() to return, with an ApiDmaCalled error code in the AlazarException. This is caught and the acquisition thread continues, but not for long...
# Unless this was caused by an abort, the demise of the main thread causes the acquisition thread to be collected. 
# At this point, everything in the worker is dead and restart is clean.
# *** What happens if an abort is sent:


    @BLACS_worker    
    class GuilessWorker(Worker):
        def init(self):
            global h5py; import labscript_utils.h5_lock, h5py
            from Queue import Queue # TODO: Python 3 compat required
            import threading
            # hard-coded again for now
            system_id = 1
            board_id  = 1
            self.board = ats.Board(systemId = system_id, boardId = board_id)
            print("Initialised AlazarTech system {:d}, board {:d}.".format(system_id, board_id))
            self.board.abortAsyncRead()
            self.acquisition_queue = Queue()
            self.acquisition_thread = threading.Thread(target=self.acquisition_loop)
            self.acquisition_thread.daemon = True
            self.acquisition_exception = None
            self.acquisition_done = threading.Event()
            self.acquisition_thread.start()
            self.aborting = False
                
        def transition_to_buffered(self,device_name,h5file,initial_values,fresh):
            self.h5file = h5file # We'll need this in transition_to_manual
            self.device_name = device_name
            with h5py.File(h5file) as hdf5_file:
                print("transition_to_buffered: using "+h5file)
                self.atsparam = atsparam = labscript_utils.properties.get(hdf5_file, device_name, 'device_properties')
                #print("atsparam: " + repr(self.atsparam))

            def find_nearest(array, value):
                if not isinstance(array, np.ndarray):
                    array = np.array(array)
                ix = np.abs(array - value).argmin()
                return array[ix]   
            actual_acquisition_rate = find_nearest(atsSampleRates.keys(), atsparam['requested_acquisition_rate'])
            atsSamplesPerSec = atsSampleRates[actual_acquisition_rate]

            # Store the actual acquisition rate back as an attribute. 
            # Again, this should be done as an ACQUISITIONS table entry, but not today
            with h5py.File(h5file) as hdf5_file:
                hdf5_file['devices'][device_name].attrs.create('acquisition_rate', actual_acquisition_rate, dtype='int32')

            self.board.setCaptureClock(atsparam['clock_source_id'], atsSamplesPerSec, atsparam['clock_edge_id'],  0)    
            print('Actual samples per second: {:.0f} ({:.1f} MS/s).'.format(actual_acquisition_rate,actual_acquisition_rate/1e6))
            print('Capture clock source_id: {:d}, clock_edge_id: {:d}.'.format(atsparam['clock_source_id'], atsparam['clock_edge_id']))

            # ETR_5V means +/-5V, and is 8bit
            # So code 150 means (150-128)/128 * 5V = 860mV.
            self.board.setExternalTrigger(atsparam['exttrig_coupling_id'], atsparam['exttrig_range_id'])
            print("Trigger coupling_id: {:d}, range_id: {:d}.".format(atsparam['exttrig_coupling_id'], atsparam['exttrig_range_id']))
            
            self.board.setTriggerOperation( atsparam['trig_operation'], 
                                            atsparam['trig_engine_id1'], atsparam['trig_source_id1'], atsparam['trig_slope_id1'], atsparam['trig_level_id1'], 
                                            atsparam['trig_engine_id2'], atsparam['trig_source_id2'], atsparam['trig_slope_id2'], atsparam['trig_level_id2'] )
            print("Trigger operation set to operation: {:d}".format(atsparam['trig_operation']))
            print("Trigger engine 1 set to {:d}, source: {:d}, slope: {:d}, level: {:d}.".format(
                        atsparam['trig_engine_id1'], atsparam['trig_source_id1'], atsparam['trig_slope_id1'], atsparam['trig_level_id1']))
            print("Trigger engine 2 set to {:d}, source: {:d}, slope: {:d}, level: {:d}.".format(            
                        atsparam['trig_engine_id2'], atsparam['trig_source_id2'], atsparam['trig_slope_id2'], atsparam['trig_level_id2']))

            # We will deal with trigger delays in labscript!
            triggerDelay_sec = 0
            triggerDelay_samples = int(triggerDelay_sec * actual_acquisition_rate + 0.5)
            self.board.setTriggerDelay(0)

            # NOTE: The board will wait for a for this amount of time for a trigger event.  If a trigger event does not arrive, then the
            # board will automatically trigger. Set the trigger timeout value to 0 to force the board to wait forever for a trigger event.
            # LDT: We'll leave this set to zero for now. We timeout on the readout, not on the trigger. 
            # But we should probably check if we ever got a trigger!
            self.board.setTriggerTimeOut(0)
            #print("Trigger timeout set to infinity")

            # Configure AUX I/O connector.
            # By default this emits the sample clock; not sure if this is before or after decimation
            self.board.configureAuxIO(ats.AUX_OUT_TRIGGER, 0) # Second param is a dummy value when AUX_OUT_TRIGGER
            #print("Aux output set to sample clock.")

            try:
                chA_range_id = atsRanges[atsparam['chA_input_range']]
            except KeyError:
                print("Voltage setting {:d}mV for Channel A is not recognised in atsapi. Make sure you use millivolts.".format(atsparam['chA_input_range']))
            self.board.inputControl( ats.CHANNEL_A, atsparam['chA_coupling_id'], chA_range_id, atsparam['chA_impedance_id'])
            self.board.setBWLimit(ats.CHANNEL_A, atsparam['chA_bw_limit'])
            print("Channel A input full scale: {:d}, coupling: {:d}, impedance: {:d}, bandwidth limit: {:d}.".format(
                atsparam['chA_input_range'], atsparam['chA_coupling_id'], atsparam['chA_impedance_id'], atsparam['chA_bw_limit']))

            try:
                chB_range_id = atsRanges[atsparam['chB_input_range']]
            except KeyError:
                print("Voltage setting {:d}mV for Channel B is not recognised in atsapi. Make sure you use millivolts.".format(atsparam['chB_input_range']))
            self.board.inputControl( ats.CHANNEL_B, atsparam['chB_coupling_id'], chB_range_id, atsparam['chB_impedance_id'])
            self.board.setBWLimit(ats.CHANNEL_B, atsparam['chB_bw_limit'])
            print("Channel B input full scale: {:d}, coupling: {:d}, impedance: {:d}, bandwidth limit: {:d}.".format(
                atsparam['chB_input_range'], atsparam['chB_coupling_id'], atsparam['chB_impedance_id'], atsparam['chB_bw_limit']))

            # ====== Acquisition code starts here =====         
            self.samplesPerBuffer=204800 # This is a magic number and should at the very least move up
            self.oneM=2**20
            self.timeout = 60000 # This should be determined by experiment run time. 

            # Check which channels we are acquiring
            #channels = ats.CHANNEL_A | ats.CHANNEL_B
            self.channels = atsparam['channels']
            if not (self.channels & ats.CHANNEL_A or self.channels & ats.CHANNEL_B):
                raise LabscriptError, "You must select either Channel-A or Channel-B, or both. Zero or >2 channels not supported."
            self.channelCount = 0
            for c in ats.channels:
                self.channelCount += (c & self.channels == c)

            # Compute the number of bytes per record and per buffer
            memorySize_samples, self.bitsPerSample = self.board.getChannelInfo()
            self.bytesPerDatum = (self.bitsPerSample.value + 7) // 8

            # One 'sample' is one datum from each channel
            print("bytesPerDatum = {:d}. channelcount = {:d}.".format(self.bytesPerDatum, self.channelCount))
            self.bytesPerBuffer = self.bytesPerDatum * self.channelCount * self.samplesPerBuffer 

            # Calculate the number of buffers in the acquisition
            self.samplesPerAcquisition = int(actual_acquisition_rate * atsparam['acquisition_duration'] + 0.5)
            memoryPerAcquisition = self.bytesPerDatum * self.samplesPerAcquisition * self.channelCount
            self.buffersPerAcquisition = ((self.samplesPerAcquisition + self.samplesPerBuffer - 1) //
                                           self.samplesPerBuffer)
            print('Acquiring for {:5.3f}s generates {:5.3f} MS ({:5.3f} MB total)'.format(
                atsparam['acquisition_duration'], self.samplesPerAcquisition/1e6, memoryPerAcquisition/self.oneM))
            print('Buffers are {:5.3f} MS and {:d} bytes. Allocating {:d} buffers... '.format(self.samplesPerBuffer/1e6,self.bytesPerBuffer,self.buffersPerAcquisition),end='')
            self.board.setRecordSize(0,self.samplesPerBuffer)

            # Allocate buffers
            # We know that disk can't keep up, so we preallocate all buffers
            sample_type = ctypes.c_uint16 # It's 16bit, let's not stuff around
            self.buffers=[]
            for i in range(self.buffersPerAcquisition):
                self.buffers.append(ats.DMABuffer(sample_type, self.bytesPerBuffer))
                #print('{:d} '.format(i),end="")
            print('done.')

            # This works but ADMA_ALLOC_BUFFERS is questionable because we have allocated the buffers (well atsapi.py buffer class has)
            acqflags = ats.ADMA_TRIGGERED_STREAMING | ats.ADMA_ALLOC_BUFFERS | ats.ADMA_FIFO_ONLY_STREAMING
            #print("Acqflags in decimal: {:d}".format(acqflags))

            # This does not actually start the capture, it just sets it up
            self.board.beforeAsyncRead(self.channels,
                                  0,                 # Trig offset, must be 0
                                  self.samplesPerBuffer,
                                  1,                 # Must be 1
                                  0x7FFFFFFF,        # Ignored
                                  acqflags)

            self.acquisition_queue.put('start')
            return {} # ? Check this

        # This becomes a long-running thread which fills the buffers allocated in the main thread.
        # Buffers are saved and freed in transition_to_manual().
        def acquisition_loop(self):
            while True:
                command = self.acquisition_queue.get()
                assert command == 'start'
                print("acquisition thread: starting new acquisition")
                start = time.clock()               # Keep track of when acquisition started
                self.acquisition_exception = None  # This is a fresh trip through the acquisition loop, no exception has occurred yet!
                try:
                    print("Capturing {:d} buffers. ".format(self.buffersPerAcquisition), end="")
                    buffersCompleted = 0; bytesTransferred = 0
                    print('Read buffer:',end="")
                    while (buffersCompleted < self.buffersPerAcquisition and not self.aborting):
                        buffer = self.buffers[buffersCompleted]
                        self.board.waitNextAsyncBufferComplete(buffer.addr, self.bytesPerBuffer, timeout_ms=self.timeout)
                        buffersCompleted += 1
                        print(' {:d}'.format(buffersCompleted),end="")
                        bytesTransferred += buffer.size_bytes
                except ats.AlazarException as e:
                    # Assume that if we got here it was due to an exception in waitNextAsyncBufferComplete. 
                    errstring, funcname, arguments, retCode = e.args
                    print("\n\nAPI error string is: {:s}".format(errstring))
                    self.acquisition_exception = sys.exc_info() # Even if in an abort, we still process this exception up to the main thread via shared state
                    print("acquisition thread: acquisition_exception is {:s}".format(self.acquisition_exception))
                    continue # Next iteration of the infinite loop, wait for next acquisition, or have the main thread decide to die
                except Exception as e:
                    print("Got some other exception {:s}".format(e))
                    self.acquisition_exception = sys.exc_info()
                    continue # Next iteration of the infinite loop, wait for next acquisition, or have the main thread decide to die
                finally:
                    self.board.abortAsyncRead()
                    self.acquisition_done.set()
                if self.aborting:
                    print("acquisition thread: capture aborted.")
                    continue
                transferTime_sec = time.clock() - start # Compute the total transfer time, and display performance information.
                print(". Capture completed in {:3.2f}s.".format(transferTime_sec))
                buffersPerSec = 0; bytesPerSec = 0
                if transferTime_sec > 0:
                    buffersPerSec = buffersCompleted / transferTime_sec
                    bytesPerSec = bytesTransferred / transferTime_sec
                print("Captured {:d} buffers ({:3.2f} buffers/s), transferred {:d} bytes ({:.1f} MB/s).".format(
                    buffersCompleted, buffersPerSec, bytesTransferred, bytesPerSec/self.oneM))
           
        def program_manual(self,values):
            return values

        def to_volts(self, zeroToFullScale, buf):
            offset = float(2**(self.bitsPerSample.value-1))
            return (np.asfarray(buf, np.float32)-offset)/offset * zeroToFullScale * 0.001 

        # This helper function waits for the acquisition_loop thread to finish the acquisition,
        # either successfully or after an exception.
        # It is used by transition_to_manual() and abort().
        # The acquisition_done flag should already be set, 
        # if it can't get this after a brief delay then something has gone wrong with acquisition overrun and it will complain and die in the main thread,
        # causing the whole lot to die. 
        def wait_acquisition_complete(self):
            try:
                if not self.acquisition_done.wait(timeout=2) and not self.aborting:
                    raise Exception('Waiting for acquisition to complete timed out')
                print("acquisition_exception is {:s}".format(self.acquisition_exception))
                if self.acquisition_exception is not None and not self.aborting:
                    raise self.acquisition_exception
            finally:
                self.board.abortAsyncRead()      # This ensures that the blocking call in the acquisition thread is aborted.
                self.acquisition_done.clear()
                self.acquisition_exception = None

        def transition_to_manual(self):
            #print("transition_to_manual: using " + self.h5file)
            self.wait_acquisition_complete()  # Waits on the acquisition thread, and manages the lock
            # Write data to HDF5 file
            with h5py.File(self.h5file) as hdf5_file:
                grp = hdf5_file.create_group('/data/traces/'+self.device_name)
                if self.channels & ats.CHANNEL_A:
                    dsetA    = grp.create_dataset('channelA',    (self.samplesPerAcquisition,), dtype='float32')
                    dsetAraw = grp.create_dataset('rawsamplesA', (self.samplesPerAcquisition,), dtype='uint16')
                if self.channels & ats.CHANNEL_B:
                    dsetB    = grp.create_dataset('channelB',    (self.samplesPerAcquisition,), dtype='float32')
                    dsetBraw = grp.create_dataset('rawsamplesB', (self.samplesPerAcquisition,), dtype='uint16')        
                start = 0
                print('Writing buffers to HDF5... ',end='')
                samplesToProcess = self.samplesPerAcquisition
                # This slightly silly logic assumes that if you are acquiring only one channel then it's chA. 
                # This should be redone
                for buf in self.buffers:
                    bufferData = buf.buffer
                    #lastI shortens the buffer aquisition at the end of a sample, ie last buffer. I'm sure this could be nicer!
                    lastI = (samplesToProcess if (samplesToProcess < self.samplesPerBuffer) else self.samplesPerBuffer) * self.channelCount
                    end = start+len(bufferData[0 : lastI])//self.channelCount
                    if self.channels & ats.CHANNEL_A:
                        dsetAraw[start : end] = bufferData[0 : lastI : self.channelCount]
                        dsetA[   start : end] = self.to_volts(self.atsparam['chA_input_range'],bufferData[0 : lastI : self.channelCount])
                    if self.channels & ats.CHANNEL_B:
                        dsetBraw[start : end] = bufferData[1 : lastI : self.channelCount]
                        dsetB[   start : end] = self.to_volts(self.atsparam['chB_input_range'],bufferData[1 : lastI : self.channelCount])
                    samplesToProcess -= self.samplesPerBuffer
                    start += self.samplesPerBuffer
                print('finished with HDF5. ',end='')
            print("Freeing buffers... ",end="")
            for buf in self.buffers: buf.__exit__()
            self.buffers = []
            print('done.',end="\n\n")
            return True

        def abort(self):
            print("aborting! ... ")
            self.aborting = True
            self.wait_acquisition_complete()
            self.aborting = False
            print("abort complete.")
            return True

        def abort_buffered(self):
            print("abort_buffered: ...")
            return self.abort()

        def abort_transition_to_buffered(self):
            print("abort_transition_to_buffered: ...")
            return self.abort()