#####################################################################
#                                                                   #
# /NI_DAQmx/tab.py                                                  #
#                                                                   #
# Copyright 2018, Monash University, JQI, Christopher Billington    #
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

from blacs.device_base_class import DeviceTab


class NI_DAQmxTab(DeviceTab):
    def initialise_GUI(self):
        # Get capabilities from connection table properties:
        connection_table = self.settings['connection_table']
        properties = connection_table.find_by_name(self.device_name).properties

        num_AO = properties['num_AO']
        num_AI = properties['num_AI']
        DO_ports = properties['DO_ports']
        num_PFI = properties['num_PFI']
        num_counters = properties['num_counters']

        AO_base_units = 'V'
        AO_base_min, AO_base_max = properties['range_AO']
        AO_base_step = 0.1
        AO_base_decimals = 3

        clock_limit = properties['clock_limit']
        clock_terminal = properties['clock_terminal']
        clock_mirror_terminal = properties['clock_mirror_terminal']
        static_AO = properties['static_AO']
        static_DO = properties['static_DO']

        # And the Measurement and Automation Explorer (MAX) name we will need to
        # communicate with the device:
        self.MAX_name = properties['MAX_name']

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
        for port_str, num_DO in DO_ports.items():
            DO_prop = {}
            for line in range(num_DO):
                DO_prop['%s/line%d' % (port_str, line)] = {}
            DO_proplist.append((port_str, DO_prop))

        PFI_prop = {}
        for i in range(num_PFI):
            PFI_prop['PFI%d' % i] = {}

        # Create the output objects
        self.create_analog_outputs(AO_prop)

        # Create widgets for outputs defined so far (i.e. analog outputs only)
        _, AO_widgets, _ = self.auto_create_widgets()

        # now create the digital output objects
        for _, DO_prop in DO_proplist:
            self.create_digital_outputs(DO_prop)
        self.create_digital_outputs(PFI_prop)

        # Manually create the digital output widgets so they are grouped separately
        DO_widgets_by_port = {}
        for port_str, DO_prop in DO_proplist:
            DO_widgets_by_port[port_str] = self.create_digital_widgets(DO_prop)
        PFI_widgets = self.create_digital_widgets(PFI_prop)

        # Auto place the widgets in the UI, specifying sort keys for ordering them:
        widget_list = [("Analog outputs", AO_widgets, _split_conn_AO)]
        for port_str, DO_widgets in sorted(DO_widgets_by_port.items()):
            name = "Digital outputs: %s" % port_str
            widget_list.append((name, DO_widgets, _split_conn_DO))
        widget_list.append(("PFI outputs", PFI_widgets, _split_conn_PFI))

        self.auto_place_widgets(*widget_list)

        # Create and set the primary worker
        self.create_worker(
            "main_worker",
            Ni_DAQmxWorker,
            {
                'MAX_name': self.MAX_name,
                'Vmin': AO_base_min,
                'Vmax': AO_base_max,
                'num_AO': num_AO,
                'DO_ports': DO_ports,
                'num_PFI': num_PFI,
                'clock_limit': clock_limit,
                'clock_terminal': clock_terminal,
                'clock_mirror_terminal': clock_mirror_terminal,
                'static_AO': static_AO,
                'static_DO': static_DO,
            },
        )
        self.primary_worker = "main_worker"

        # Only need an acquisition worker if we have analog inputs:
        if num_AI > 0:
            self.create_worker(
                "acquisition_worker",
                Ni_DAQmxAcquisitionWorker,
                {'MAX_name': self.MAX_name},
            )
            self.add_secondary_worker("acquisition_worker")

        # We only need a wait monitor worker if we are if fact the device with
        # the wait monitor input.
        with h5py.File(connection_table.filepath, 'r') as f:
            waits = f['waits']
            wait_acq_device = waits.attrs['wait_monitor_acquisition_device']
            wait_acq_connection = waits.attrs['wait_monitor_acquisition_connection']
            wait_timeout_device = waits.attrs['wait_monitor_timeout_device']
            wait_timeout_connection = waits.attrs['wait_monitor_timeout_connection']
            try:
                timeout_trigger_type = waits.attrs['wait_monitor_timeout_trigger_type']
            except KeyError:
                timeout_trigger_type = 'rising'

        if wait_acq_device == self.device_name:
            if wait_timeout_device != self.device_name:
                msg = """The wait monitor acquisition device must be the same as the
                    wait timeout device."""
                raise RuntimeError(msg)

            if num_counters == 0:
                msg = "Device cannot be a wait monitor as it has no counter inputs"
                raise RuntimeError(msg)

            # Using this workaround? Default to False in case not present in file:
            counter_bug_workaround = properties.get(
                "DAQmx_waits_counter_bug_workaround", False
            )

            self.create_worker(
                "wait_monitor_worker",
                Ni_DAQmxWaitMonitorWorker,
                {
                    'MAX_name': self.MAX_name,
                    'wait_acq_connection': wait_acq_connection,
                    'wait_timeout_connection': wait_timeout_connection,
                    'timeout_trigger_type': timeout_trigger_type,
                    'counter_bug_workaround': counter_bug_workaround,
                },
            )
            self.add_secondary_worker("wait_monitor_worker")

        # Set the capabilities of this device
        self.supports_remote_value_check(False)
        self.supports_smart_programming(False)
