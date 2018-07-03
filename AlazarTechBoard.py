# A labscript device class for data acquisition boards made by Alazar Technologies Inc (ATS)
# Hacked up from NIBoard.py by LDT 2017-01-26
#
# Copyright (c) Monash University 2017

if __name__ != "__main__":
    import numpy as np
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
    # Anything to do with onboard memory
    # Anything "for scanning"
    
        @set_passed_properties(property_names = {
            "device_properties":["ats_system_id", "ats_board_id",
                             "requested_acquisition_rate",
                             "clock_source_id", "sample_rate_id_or_value", "clock_edge_id", "decimation",
                             "trig_operation",
                             "trig_engine_id1", "trig_source_id1", "trig_slope_id1",  "trig_level_id1",
                             "trig_engine_id2", "trig_source_id2", "trig_slope_id2", "trig_level_id2",
                             "exttrig_coupling_id", "exttrig_range_id",
                             "trig_delay_samples", "trig_timeout_10usecs", "input_range"]
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

        def transition_to_buffered(self,device_name,h5file,initial_values,fresh):
            self.h5file = h5file # We'll need this in transition_to_manual
            with h5py.File(h5file) as hdf5_file:
                group = hdf5_file['/devices/'+device_name]
                print("transition_to_buffered: using "+h5file)
                #self.board_attributes = group.attrs.copy()
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