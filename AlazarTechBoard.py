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

# This little tangle was needed to make auto zlocking work right,
# but now that this is in BLACS we should be fine with usual h5lock imported below
#import h5_lock  # The local one in source directory! Not the system one which lives in labscript_utils.h5_lock
#h5_lock.init(host='beclogger.physics.monash.edu.au', port=7339, shared_drive_prefix='Z:', lock_timeout=60)
#import h5py

# Define some globals
#samplesPerSec = None
#actualSamplesPerSec=None
#samplesPerAcquisition=None
#samplesPerBuffer = None
#bitsPerSample = None
#channelCount = None
#zeroToFullScale = None
#buffers = []
#channels = None

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
                             "requested_acquisition_rate",
                             "clock_source_id", "sample_rate_id_or_value", "clock_edge_id", "decimation",
                             "trig_operation",
                             "trig_engine_id1", "trig_source_id1", "trig_slope_id1",  "trig_level_id1",
                             "trig_engine_id2", "trig_source_id2", "trig_slope_id2", "trig_level_id2",
                             "exttrig_coupling_id", "exttrig_range_id",
                             "trig_delay_samples", "trig_timeout_10usecs", "input_range",
                             "chA_coupling_id", "chA_range_id", "chA_impedance_id", "chA_bw_limit",
                             "chB_coupling_id", "chB_range_id", "chB_impedance_id", "chB_bw_limit",
                             ]
        })
    
        def __init__(self, name, server,
                     ats_system_id=1, ats_board_id=1,
                     requested_acquisition_rate=0, # No default for this, must be calculated and set!
                     clock_source_id         = ats.INTERNAL_CLOCK,
                     sample_rate_id_or_value = ats.SAMPLE_RATE_180MSPS,
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
                     trig_delay_samples      =0,
                     trig_timeout_10usecs    =0,
                     input_range             =4000):
            Device.__init__(self, name, None, None)
            #self.name=name
            # self.acquisition_rate = acquisition_rate
            # self.clock_terminal = clock_terminal
            # self.clock_source_id         = clock_source_id         
            # self.sample_rate_id_or_value = sample_rate_id_or_value 
            # self.clock_edge_id           = clock_edge_id           
            # self.decimation              = decimation              
            # self.trig_operation          = trig_operation          
            # self.trig_engine_id1         = trig_engine_id1         
            # self.trig_source_id1         = trig_source_id1         
            # self.trig_slope_id1          = trig_slope_id1          
            # self.trig_level_id1          = trig_level_id1          
            # self.trig_engine_id2         = trig_engine_id2         
            # self.trig_source_id2         = trig_source_id2         
            # self.trig_slope_id2          = trig_slope_id2          
            # self.trig_level_id2          = trig_level_id2          
            # self.exttrig_coupling_id     = exttrig_coupling_id     
            # self.exttrig_range_id        = exttrig_range_id        
            # self.trig_delay_samples      = trig_delay_samples      
            # self.trig_timeout_10usecs    = trig_timeout_10usecs    
            self.BLACS_connection        = server

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

    @BLACS_worker    
    class GuilessWorker(Worker):
        def init(self):
            global h5py; import labscript_utils.h5_lock, h5py
            # hard-coded again for now
            system_id = 1
            board_id  = 1
            self.board = ats.Board(systemId = system_id, boardId = board_id)
            print("Initialised AlazarTech system {:d}, board {:d}.".format(system_id, board_id))
            self.board.abortAsyncRead()
            
        def transition_to_buffered(self,device_name,h5file,initial_values,fresh):
            self.h5file = h5file # We'll need this in transition_to_manual
            with h5py.File(h5file) as hdf5_file:
                hdf5_filegroup = hdf5_file['devices'][device_name]
                print("transition_to_buffered: using "+h5file)
                self.atsparam = dict(hdf5_filegroup.attrs)
                print("atsparam: " + repr(self.atsparam))

            #    acquisitionLength_sec = globs['hobbs_acquire_time']
            #    requestedSamplesPerSec  = f['/devices/' + device_name].attrs['requested_acquisition_rate']
            #    zeroToFullScale  = f['/devices/' + device_name].attrs['input_range']
            def find_nearest(array, value):
                if not isinstance(array, np.ndarray):
                    array = np.array(array)
                ix = np.abs(array - value).argmin()
                return array[ix]
            actualSamplesPerSec = find_nearest(atsSampleRates.keys(), requestedSamplesPerSec)
            atsSamplesPerSec = atsSampleRates[actualSamplesPerSec]
            #f['/devices/' + device_name].attrs.create('acquisition_rate', actualSamplesPerSec, dtype='int32')
            board.setCaptureClock(ats.INTERNAL_CLOCK,
                              atsSamplesPerSec,
                              ats.CLOCK_EDGE_RISING,
                              0)    
            print('Samples per second {:.0f} ({:4.1f} MS/s)'.format(actualSamplesPerSec,actualSamplesPerSec/1e6))
            print("Capture clock set to ...")


            # Set 5V-range DC-coupled trigger.
            # ETR_5V means +/-5V, and is 8bit
            # So code 150 means (150-128)/128 * 5V = 860mV.
            self.board.setExternalTrigger(ats.DC_COUPLING,
                                     ats.ETR_5V)
            print("Trigger coupling and level set to ...")
            self.board.setTriggerOperation(ats.TRIG_ENGINE_OP_J,        # Low-to-high
                                      ats.TRIG_ENGINE_J,           # Use "Engine J"
                                      ats.TRIG_EXTERNAL,           # External
                                      ats.TRIGGER_SLOPE_POSITIVE,
                                      150,                         # Code for 0mV level
                                      ats.TRIG_ENGINE_K,           # The second trigger engine...
                                      ats.TRIG_DISABLE,            # ... is turned off
                                      ats.TRIGGER_SLOPE_POSITIVE,  # Dummy value
                                      150)                         # Dummy value
            print("Trigger operation set to ...")

            # We will deal with trigger delays in labscript!
            triggerDelay_sec = 0
            triggerDelay_samples = int(triggerDelay_sec * actualSamplesPerSec + 0.5)
            #self.board.setTriggerDelay(triggerDelay_samples)
            self.board.setTriggerDelay(0)

            # NOTE: The board will wait for a for this amount of time for a
            # trigger event.  If a trigger event does not arrive, then the
            # board will automatically trigger. Set the trigger timeout value
            # to 0 to force the board to wait forever for a trigger event.
            # LDT: We'll leave this set to zero for now
            triggerTimeout_sec = 0
            triggerTimeout_clocks = int(triggerTimeout_sec / 10e-6 + 0.5)
            #self.board.setTriggerTimeOut(triggerTimeout_clocks)
            self.board.setTriggerTimeOut(0)
            print("Trigger timeout set to infinity")

            # Configure AUX I/O connector
            # By default this emits the sample clock
            # Not sure if this is before or after decimation
            self.board.configureAuxIO(ats.AUX_OUT_TRIGGER,
                                 0) # Dummy value when AUX_OUT_TRIGGER
            print("Aux output set to trigger.")

            try:
                atsInputRange = atsRanges[zeroToFullScale]
                print("Voltage Scale at {:d}".format(zeroToFullScale))
            except KeyError:
                print("Voltage setting {:d}mV  is not recognised in atsapi. Make sure you use millivolts.".format(zeroToFullScale))
            board.inputControl( ats.CHANNEL_A,
                                ats.AC_COUPLING,
                                atsInputRange,
                                #ats.INPUT_RANGE_PM_400_MV,
                                #ats.IMPEDANCE_1M_OHM)
                                ats.IMPEDANCE_50_OHM)
            board.setBWLimit(ats.CHANNEL_A, 0)
            print("Channel A input set to ...")

            # Channel B captures the reference wave
            board.inputControl( ats.CHANNEL_B,
                                ats.AC_COUPLING,
                                atsInputRange,
                                #ats.INPUT_RANGE_PM_400_MV,
                                #ats.IMPEDANCE_1M_OHM)
                                ats.IMPEDANCE_50_OHM)
            board.setBWLimit(ats.CHANNEL_B, 0)
            print("Channel B input set to ...")

            return {} # ? Check this

        def program_manual(self,values):
            return values

        def transition_to_manual(self):
            print("transition_to_manual: using " + self.h5file)
            return True

        def abort(self):
            print("abort: not doing anything about it though!")
            return True

        def abort_buffered(self):
            print("abort_buffered: not doing anything about it though!")
            return self.abort()

        def abort_transition_to_buffered(self):
            print("abort_transition_to_buffered: not doing anything about it though!")
            return self.abort()