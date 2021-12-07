#####################################################################
#                                                                   #
# /labscript_devices/PrawnBlaster/blacs_tab.py                      #
#                                                                   #
# Copyright 2021, Philip Starkey                                    #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from blacs.device_base_class import (
    DeviceTab,
    define_state,
    MODE_BUFFERED,
    MODE_MANUAL,
    MODE_TRANSITION_TO_BUFFERED,
    MODE_TRANSITION_TO_MANUAL,
)
import labscript_utils.properties

from qtutils.qt import QtWidgets


class PrawnBlasterTab(DeviceTab):
    """BLACS Tab for the PrawnBlaster Device."""

    def initialise_GUI(self):
        """Initialises the Tab GUI.

        This method is called automatically by BLACS.
        """

        self.connection_table_properties = (
            self.settings["connection_table"].find_by_name(self.device_name).properties
        )

        digital_outs = {}
        for pin in self.connection_table_properties["out_pins"]:
            digital_outs[f"GPIO {pin:02d}"] = {}

        # Create a single digital output
        self.create_digital_outputs(digital_outs)
        # Create widgets for output objects
        _, _, do_widgets = self.auto_create_widgets()
        # and auto place the widgets in the UI
        self.auto_place_widgets(("Flags", do_widgets))

        # Create status labels
        self.status_label = QtWidgets.QLabel("Status: Unknown")
        self.clock_status_label = QtWidgets.QLabel("Clock status: Unknown")
        self.get_tab_layout().addWidget(self.status_label)
        self.get_tab_layout().addWidget(self.clock_status_label)

        # Set the capabilities of this device
        self.supports_smart_programming(True)

        # Create status monitor timout
        self.statemachine_timeout_add(2000, self.status_monitor)

    def get_child_from_connection_table(self, parent_device_name, port):
        """Finds the attached ClockLines.

        Args:
            parent_device_name (str): name of parent_device
            port (str): port of parent_device

        Returns:
            :class:`~labscript.ClockLine`: PrawnBlaster interal Clocklines
        """

        # Pass down channel name search to the pseudoclocks (so we can find the
        # clocklines)
        if parent_device_name == self.device_name:
            device = self.connection_table.find_by_name(self.device_name)

            for pseudoclock_name, pseudoclock in device.child_list.items():
                for child_name, child in pseudoclock.child_list.items():
                    # store a reference to the internal clockline
                    if child.parent_port == port:
                        return DeviceTab.get_child_from_connection_table(
                            self, pseudoclock.name, port
                        )

        return None

    def initialise_workers(self):
        """Initialises the PrawnBlaster Workers.

        This method is called automatically by BLACS.
        """

        # Find the COM port to be used
        com_port = str(
            self.settings["connection_table"]
            .find_by_name(self.device_name)
            .BLACS_connection
        )

        worker_initialisation_kwargs = {
            "com_port": com_port,
            "num_pseudoclocks": self.connection_table_properties["num_pseudoclocks"],
            "out_pins": self.connection_table_properties["out_pins"],
            "in_pins": self.connection_table_properties["in_pins"],
        }
        self.create_worker(
            "main_worker",
            "labscript_devices.PrawnBlaster.blacs_workers.PrawnBlasterWorker",
            worker_initialisation_kwargs,
        )
        self.primary_worker = "main_worker"

    @define_state(
        MODE_MANUAL
        | MODE_BUFFERED
        | MODE_TRANSITION_TO_BUFFERED
        | MODE_TRANSITION_TO_MANUAL,
        True,
    )
    def status_monitor(self, notify_queue=None):
        """Gets the status of the PrawnBlaster from the worker.

        When called with a queue, this function writes to the queue
        when the PrawnBlaster is waiting. This indicates the end of
        an experimental run.

        Args:
            notify_queue (:class:`~queue.Queue`): Queue to notify when
                the experiment is done.

        """

        status, clock_status, waits_pending = yield (
            self.queue_work(self.primary_worker, "check_status")
        )

        # Manual mode or aborted
        done_condition = status == 0 or status == 5

        # Update GUI status/clock status widgets
        self.status_label.setText(f"Status: {status}")
        self.clock_status_label.setText(f"Clock status: {clock_status}")

        if notify_queue is not None and done_condition and not waits_pending:
            # Experiment is over. Tell the queue manager about it, then
            # set the status checking timeout back to every 2 seconds
            # with no queue.
            notify_queue.put("done")
            self.statemachine_timeout_remove(self.status_monitor)
            self.statemachine_timeout_add(2000, self.status_monitor)

    @define_state(MODE_BUFFERED, True)
    def start_run(self, notify_queue):
        """When used as the primary Pseudoclock, this starts the run."""

        self.statemachine_timeout_remove(self.status_monitor)
        yield (self.queue_work(self.primary_worker, "start_run"))
        self.status_monitor()
        self.statemachine_timeout_add(100, self.status_monitor, notify_queue)
