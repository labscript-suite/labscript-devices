# A labscript device class for data acquisition boards made by Alazar Technologies Inc (ATS)
# Hacked up from NIboard.py by LDT 2017-01-26
#
# Copyright (c) Monash University 2017
import numpy as np
import labscript_devices.AlazarTechBoard.atsapi as ats
from labscript import Device, AnalogIn, config, set_passed_properties


class AlazarTechBoard(Device):
    allowed_children = [AnalogIn]
    description = 'Generic_Alazar_Technologies_capture_board'

# Many properties not supported. Examples include:
# AlazarSetExternalClockLevel, SetDataFormat
# Anything to do with board memory
# Anything "for scanning"
    @set_passed_properties(property_names={
        "device_properties": ["ats_system_id", "ats_board_id",
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
                 clock_source_id         = ats.INTERNAL_CLOCK,
                 sample_rate_id          = ats.SAMPLE_RATE_180MSPS,
                 clock_edge_id           = ats.CLOCK_EDGE_RISING,
                 decimation              = 0, 
                 trig_operation          = ats.TRIG_ENGINE_OP_J,
                 trig_engine_id1         = ats.TRIG_ENGINE_J,
                 trig_source_id1         = ats.TRIG_EXTERNAL,
                 trig_slope_id1          = ats.TRIGGER_SLOPE_POSITIVE,
                 trig_level_id1          = 150, # 860 mV
                 trig_engine_id2         = ats.TRIG_ENGINE_K,
                 trig_source_id2         = ats.TRIG_DISABLE,
                 trig_slope_id2          = ats.TRIGGER_SLOPE_POSITIVE,
                 trig_level_id2          = 150, # 860 mV
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
        # This line makes BLACS think the device is connected to something
        self.BLACS_connection = server

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
        input_connections = sorted(inputs)
        input_attrs = []
        acquisitions = []
        for connection in input_connections:
            input_attrs.append(self.name+'/'+connection)
            for acq in inputs[connection].acquisitions:
                acquisitions.append((connection, acq['label'], acq['start_time'],
                                     acq['end_time'], acq['wait_label'], acq['scale_factor'], acq['units']))
        acquisitions_table_dtypes = [('connection', 'S256'), ('label', 'S256'), ('start', float),
                                     ('stop', float), ('wait label', 'S256'), ('scale factor', float), ('units', 'S256')]
        acquisition_table = np.empty(
            len(acquisitions), dtype=acquisitions_table_dtypes)
        for i, acq in enumerate(acquisitions):
            acquisition_table[i] = acq
            grp = self.init_device_group(hdf5_file)
        if len(acquisition_table):  # Table must be non empty
            grp.create_dataset(
                'ACQUISITIONS', compression=config.compression, data=acquisition_table)
            self.set_property('analog_in_channels', ', '.join(
                input_attrs), location='device_properties')
