#####################################################################
#                                                                   #
# /DummyIntermediateDevice.py                                       #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################


# This file represents a dummy labscript device for purposes of testing BLACS
# and labscript. The device is a Intermediate Device, and can be attached to
# a pseudoclock in labscript in order to test the pseudoclock behaviour
# without needing a real Intermediate Device.
#
# You can attach an arbitrary number of outputs to this device, however we
# currently only support outputs of type AnalogOut and DigitalOut. It would be
# easy to extend this is anyone needed further functionality.


from labscript_devices import (
    BLACS_tab,
    runviewer_parser,
)
from labscript import (
    IntermediateDevice,
    DigitalOut,
    AnalogOut,
    config,
    set_passed_properties,
)
from labscript_devices.NI_DAQmx.utils import split_conn_AO, split_conn_DO
import numpy as np
import labscript_utils.h5_lock  # noqa: F401
import h5py

from blacs.device_base_class import DeviceTab
from blacs.tab_base_classes import Worker


class DummyIntermediateDevice(IntermediateDevice):

    description = 'Dummy IntermediateDevice'

    # If this is updated, then you need to update generate_code to support whatever
    # types you add
    allowed_children = [DigitalOut, AnalogOut]

    @set_passed_properties(
        property_names={
            "connection_table_properties": [
                "AO_range",
                "num_AO",
                "ports",
                "clock_limit",
            ],
            "device_properties": [],
        }
    )
    def __init__(
        self,
        name,
        parent_device=None,
        AO_range=[-10.0, 10.0],
        num_AO=4,
        ports={'port0': {'num_lines': 32, 'supports_buffered': True}},
        clock_limit=1e6,
        **kwargs,
    ):
        self.AO_range = AO_range
        self.num_AO = num_AO
        self.ports = ports if ports is not None else {}
        self.clock_limit = clock_limit
        self.BLACS_connection = 'dummy_connection'
        IntermediateDevice.__init__(self, name, parent_device, **kwargs)

    def generate_code(self, hdf5_file):
        IntermediateDevice.generate_code(self, hdf5_file)
        group = self.init_device_group(hdf5_file)

        clockline = self.parent_device
        pseudoclock = clockline.parent_device
        times = pseudoclock.times[clockline]

        # out_table = np.empty((len(times),len(self.child_devices)), dtype=np.float32)
        # determine dtypes
        dtypes = []
        for device in self.child_devices:
            if isinstance(device, DigitalOut):
                device_dtype = np.int8
            elif isinstance(device, AnalogOut):
                device_dtype = np.float64
            dtypes.append((device.connection, device_dtype))

        # create dataset
        out_table = np.zeros(len(times), dtype=dtypes)
        for device in self.child_devices:
            out_table[device.connection][:] = device.raw_output

        group.create_dataset('OUTPUTS', compression=config.compression, data=out_table)


@BLACS_tab
class DummyIntermediateDeviceTab(DeviceTab):
    def initialise_GUI(self):
        # Get capabilities from connection table properties:
        connection_table = self.settings['connection_table']
        properties = connection_table.find_by_name(self.device_name).properties

        num_AO = properties['num_AO']
        # num_DO = properties['num_DO']
        ports = properties['ports']

        AO_base_units = 'V'
        if num_AO > 0:
            AO_base_min, AO_base_max = properties['AO_range']
        else:
            AO_base_min, AO_base_max = None, None
        AO_base_step = 0.1
        AO_base_decimals = 3

        # Create output objects:
        AO_prop = {}
        for i in range(num_AO):
            AO_prop['ao%d' % i] = {
                'base_unit': AO_base_units,
                'min': AO_base_min,
                'max': AO_base_max,
                'step': AO_base_step,
                'decimals': AO_base_decimals,
            }

        DO_proplist = []
        DO_hardware_names = []
        for port_num in range(len(ports)):
            port_str = 'port%d' % port_num
            port_props = {}
            for line in range(ports[port_str]['num_lines']):
                hardware_name = 'port%d/line%d' % (port_num, line)
                port_props[hardware_name] = {}
                DO_hardware_names.append(hardware_name)
            DO_proplist.append((port_str, port_props))

        # Create the output objects
        self.create_analog_outputs(AO_prop)

        # Create widgets for outputs defined so far (i.e. analog outputs only)
        _, AO_widgets, _ = self.auto_create_widgets()

        # now create the digital output objects one port at a time
        for _, DO_prop in DO_proplist:
            self.create_digital_outputs(DO_prop)

        # Manually create the digital output widgets so they are grouped separately
        DO_widgets_by_port = {}
        for port_str, DO_prop in DO_proplist:
            DO_widgets_by_port[port_str] = self.create_digital_widgets(DO_prop)

        # Auto place the widgets in the UI, specifying sort keys for ordering them:
        widget_list = [("Analog outputs", AO_widgets, split_conn_AO)]
        for port_num in range(len(ports)):
            port_str = 'port%d' % port_num
            DO_widgets = DO_widgets_by_port[port_str]
            name = "Digital outputs: %s" % port_str
            if ports[port_str]['supports_buffered']:
                name += ' (buffered)'
            else:
                name += ' (static)'
            widget_list.append((name, DO_widgets, split_conn_DO))
        self.auto_place_widgets(*widget_list)

        # Create and set the primary worker
        self.create_worker(
            "main_worker",
            DummyIntermediateDeviceWorker,
            {
                'Vmin': AO_base_min,
                'Vmax': AO_base_max,
                'num_AO': num_AO,
                'ports': ports,
                'DO_hardware_names': DO_hardware_names,
            },
        )
        self.primary_worker = "main_worker"

        # Set the capabilities of this device
        self.supports_remote_value_check(False)
        self.supports_smart_programming(False)


class DummyIntermediateDeviceWorker(Worker):
    def init(self):
        pass

    def get_output_table(self, h5file, device_name):
        """Return the OUTPUT table from the file, or None if it does not exist."""
        with h5py.File(h5file, 'r') as hdf5_file:
            group = hdf5_file['devices'][device_name]
            try:
                return group['OUTPUTS'][:]
            except KeyError:
                return None

    def program_manual(self, front_panel_values):
        return front_panel_values

    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):
        # Get the data to be programmed into the output tasks:
        outputs = self.get_output_table(h5file, device_name)

        # Collect the final values of the outputs
        final_values = dict(zip(outputs.dtype.names, outputs[-1]))

        return final_values

    def transition_to_manual(self, abort=False):
        return True

    def abort_transition_to_buffered(self):
        return self.transition_to_manual(True)

    def abort_buffered(self):
        return self.transition_to_manual(True)

    def shutdown(self):
        pass


@runviewer_parser
class DummyIntermediateDeviceParser(object):
    def __init__(self, path, device):
        self.path = path
        self.name = device.name
        self.device = device

    def get_traces(self, add_trace, clock=None):
        times, clock_value = clock[0], clock[1]

        clock_indices = np.where((clock_value[1:] - clock_value[:-1]) == 1)[0] + 1
        # If initial clock value is 1, then this counts as a rising edge (clock should
        # be 0 before experiment) but this is not picked up by the above code. So we
        # insert it!
        if clock_value[0] == 1:
            clock_indices = np.insert(clock_indices, 0, 0)
        clock_ticks = times[clock_indices]

        # Get the output table from the experiment shot file
        with h5py.File(self.path, 'r') as hdf5_file:
            outputs = hdf5_file[f"devices/{self.name}/OUTPUTS"][:]

        traces = {}

        for channel in outputs.dtype.names:
            traces[channel] = (clock_ticks, outputs[channel])

        for channel_name, channel in self.device.child_list.items():
            if channel.parent_port in traces:
                trace = traces[channel.parent_port]
                add_trace(channel_name, trace, self.name, channel.parent_port)

        return {}
