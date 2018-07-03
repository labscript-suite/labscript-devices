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
                self.atsparam = atsparam = dict(hdf5_filegroup.attrs)
                print("atsparam: " + repr(self.atsparam))

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
            print('Samples per second {:.0f} ({:4.1f} MS/s)'.format(actual_acquisition_rate,actual_acquisition_rate/1e6))
            print('Capture clock source_id: {:d}, clock_edge_id: {:d}'.format(atsparam['clock_source_id'], atsparam['clock_edge_id']))

            # ETR_5V means +/-5V, and is 8bit
            # So code 150 means (150-128)/128 * 5V = 860mV.
            self.board.setExternalTrigger(atsparam['exttrig_coupling_id'], atsparam['exttrig_range_id'])
            print("Trigger coupling_id: {:d}, range_id: {:d}".format(atsparam['exttrig_coupling_id'], atsparam['exttrig_range_id']))
            
            self.board.setTriggerOperation( atsparam['trig_operation'], 
                                            atsparam['trig_engine_id1'], atsparam['trig_source_id1'], atsparam['trig_slope_id1'], atsparam['trig_level_id1'], 
                                            atsparam['trig_engine_id2'], atsparam['trig_source_id2'], atsparam['trig_slope_id2'], atsparam['trig_level_id2'] )
            print("Trigger operation set to operation: {:d}".format(atsparam['trig_operation']))
            print("Trigger engine 1 set to {:d}, source: {:d}, slope: {:d}, level: {:d},".format(
                        atsparam['trig_engine_id1'], atsparam['trig_source_id1'], atsparam['trig_slope_id1'], atsparam['trig_level_id1']))
            print("Trigger engine 2 set to {:d}, source: {:d}, slope: {:d}, level: {:d},".format(            
                        atsparam['trig_engine_id2'], atsparam['trig_source_id2'], atsparam['trig_slope_id2'], atsparam['trig_level_id2']))

            # We will deal with trigger delays in labscript!
            triggerDelay_sec = 0
            triggerDelay_samples = int(triggerDelay_sec * actual_acquisition_rate + 0.5)
            self.board.setTriggerDelay(0)

            # NOTE: The board will wait for a for this amount of time for a
            # trigger event.  If a trigger event does not arrive, then the
            # board will automatically trigger. Set the trigger timeout value
            # to 0 to force the board to wait forever for a trigger event.
            # LDT: We'll leave this set to zero for now
            triggerTimeout_sec = 0
            triggerTimeout_clocks = int(triggerTimeout_sec / 10e-6 + 0.5)
            self.board.setTriggerTimeOut(0)
            print("Trigger timeout set to infinity")

            # Configure AUX I/O connector
            # By default this emits the sample clock; not sure if this is before or after decimation
            self.board.configureAuxIO(ats.AUX_OUT_TRIGGER,
                                 0) # Dummy value when AUX_OUT_TRIGGER
            print("Aux output set to sample clock.")

            try:
                chA_range_id = atsRanges[atsparam['chA_input_range']]
            except KeyError:
                print("Voltage setting {:d}mV for Channel A is not recognised in atsapi. Make sure you use millivolts.".format(atsparam['chA_input_range']))
            self.board.inputControl( ats.CHANNEL_A, atsparam['chA_coupling_id'], chA_range_id, atsparam['chA_impedance_id'])
            self.board.setBWLimit(ats.CHANNEL_A, atsparam['chA_bw_limit'])
            print("Channel A input full scale: {:d}, coupling: {:d}, impedance: {:d}, bandwidth limit: {:d}".format(
                atsparam['chA_input_range'], atsparam['chA_coupling_id'], atsparam['chA_impedance_id'], atsparam['chA_bw_limit']))

            try:
                chB_range_id = atsRanges[atsparam['chB_input_range']]
            except KeyError:
                print("Voltage setting {:d}mV for Channel B is not recognised in atsapi. Make sure you use millivolts.".format(atsparam['chB_input_range']))
            self.board.inputControl( ats.CHANNEL_B, atsparam['chB_coupling_id'], chB_range_id, atsparam['chB_impedance_id'])
            self.board.setBWLimit(ats.CHANNEL_B, atsparam['chB_bw_limit'])
            print("Channel B input full scale: {:d}, coupling: {:d}, impedance: {:d}, bandwidth limit: {:d}".format(
                atsparam['chB_input_range'], atsparam['chB_coupling_id'], atsparam['chB_impedance_id'], atsparam['chB_bw_limit']))
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