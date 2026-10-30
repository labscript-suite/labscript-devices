#####################################################################
#                                                                   #
# /labscript_devices/NarwhalPulseGenerator/blacs_tabs.py            #
#                                                                   #
# Copyright 2026, Christopher Billington                            #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
# Parts of this file are derived from the Narwhal Devices labscript #
# driver, Copyright (c) 2020 Rory Speirs, which is licensed under   #
# the MIT License. See NARWHAL-DEVICES-MIT-LICENSE.txt in this      #
# directory.                                                        #
#                                                                   #
#####################################################################
import time
from datetime import datetime

from blacs.device_base_class import DeviceTab, define_state, MODE_BUFFERED, MODE_MANUAL
import qtutils.icons  # noqa: F401
from qtutils.icons import Icon
from qtutils.iconlabel import IconLabel
from qtutils.qt import QtCore, QtGui, QtWidgets

from .driver import (
    ACCEPT_HARDWARE_TRIGGER,
    CYCLE,
    MAX_POWERLINE_DELAY,
    MAX_TRIGGER_OUT_DELAY,
    MAX_TRIGGER_OUT_LENGTH,
    RUN_MODES,
)
from .labscript_devices import N_CHANNELS


class _SpinBox(QtWidgets.QDoubleSpinBox):
    """A spin box that the mouse wheel changes only when it has focus."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setKeyboardTracking(False)

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class _ComboBox(QtWidgets.QComboBox):
    """A combo box that the mouse wheel changes only when it has focus."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class NarwhalPulseGeneratorTab(DeviceTab):
    #: Period of the status monitor in manual mode, in ms.
    STATUS_MONITOR_PERIOD = 1000
    #: Longest time the worker blocks waiting for the end of a run before the tab
    #: queues the wait again, in seconds. An abort is processed between two waits.
    RUN_FINISHED_WAIT_CHUNK = 0.5

    def initialise_GUI(self):
        self.connection_table_properties = (
            self.settings["connection_table"].find_by_name(self.device_name).properties
        )
        self.create_digital_outputs({f"channel {n}": {} for n in range(N_CHANNELS)})
        _, _, do_widgets = self.auto_create_widgets()
        self.auto_place_widgets(
            ("Channels", do_widgets, lambda channel: int(channel.split()[1]))
        )
        self.get_tab_layout().addWidget(self._make_controls())
        self.supports_remote_value_check(True)
        self.notify_queue = None
        self.statemachine_timeout_add(self.STATUS_MONITOR_PERIOD, self.status_monitor)
        self.get_device_info()

    def _make_controls(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)

        # Manual control:
        row = QtWidgets.QHBoxLayout()
        row.addStretch()
        row.addWidget(QtWidgets.QLabel("Run mode:"))
        self.run_mode_combo = _ComboBox()
        self.run_mode_combo.addItems(RUN_MODES)
        self.run_mode_combo.currentTextChanged.connect(self.run_mode_changed)
        row.addWidget(self.run_mode_combo)
        self.start_button = self._button(":/qtutils/fugue/control", "Start", self.start)
        self.pause_button = self._button(
            ":/qtutils/fugue/control-pause", "Software run enable", self.pause, checkable=True
        )
        self.stop_button = self._button(
            ":/qtutils/fugue/control-stop-square", "Stop after the current run", self.stop
        )
        self.reset_button = self._button(":/qtutils/fugue/arrow-circle", "Reset", self.reset)
        for button in [self.start_button, self.pause_button, self.stop_button, self.reset_button]:
            row.addWidget(button)
        row.addStretch()
        layout.addLayout(row)

        grid = QtWidgets.QGridLayout()
        layout.addLayout(grid)

        # Status:
        form = self._group(grid, "Status", 0, 0)
        self.running_label = IconLabel()
        self.software_enable_label = IconLabel()
        self.hardware_enable_label = IconLabel()
        self.current_address_label = QtWidgets.QLabel()
        self.final_address_label = QtWidgets.QLabel()
        self.run_time_label = QtWidgets.QLabel()
        form.addRow("Running", self.running_label)
        form.addRow("Run enable (software)", self.software_enable_label)
        form.addRow("Run enable (hardware)", self.hardware_enable_label)
        form.addRow("Current address", self.current_address_label)
        form.addRow("Final address", self.final_address_label)
        form.addRow("Run time", self.run_time_label)

        # Trigger in:
        form = self._group(grid, "Trigger in", 0, 1)
        self.accept_trigger_combo = _ComboBox()
        self.accept_trigger_combo.addItems(ACCEPT_HARDWARE_TRIGGER)
        self.accept_trigger_combo.currentTextChanged.connect(self.accept_trigger_changed)
        form.addRow("Accept hardware trigger", self.accept_trigger_combo)
        self.powerline_checkbox = QtWidgets.QCheckBox()
        self.powerline_checkbox.toggled.connect(self.trigger_on_powerline_toggled)
        form.addRow("Trigger on powerline", self.powerline_checkbox)
        self.powerline_delay_spinbox = _SpinBox(
            minimum=0, maximum=MAX_POWERLINE_DELAY * CYCLE * 1e3, decimals=5, suffix=" ms"
        )
        self.powerline_delay_spinbox.editingFinished.connect(self.powerline_delay_changed)
        form.addRow("Powerline trigger delay", self.powerline_delay_spinbox)

        # Trigger out:
        form = self._group(grid, "Trigger out", 1, 0)
        self.trigger_out_length_spinbox = _SpinBox(
            minimum=0,
            maximum=MAX_TRIGGER_OUT_LENGTH * CYCLE * 1e6,
            decimals=2,
            singleStep=0.01,
            suffix=" µs",
        )
        self.trigger_out_length_spinbox.editingFinished.connect(self.trigger_out_length_changed)
        form.addRow("Length", self.trigger_out_length_spinbox)
        self.trigger_out_delay_spinbox = _SpinBox(
            minimum=0, maximum=MAX_TRIGGER_OUT_DELAY * CYCLE, decimals=8, suffix=" s"
        )
        self.trigger_out_delay_spinbox.editingFinished.connect(self.trigger_out_delay_changed)
        form.addRow("Delay", self.trigger_out_delay_spinbox)

        # Synchronisation:
        form = self._group(grid, "Synchronisation", 1, 1)
        self.clock_source_label = QtWidgets.QLabel()
        self.powerline_frequency_label = QtWidgets.QLabel()
        form.addRow("Reference clock", self.clock_source_label)
        form.addRow("Powerline", self.powerline_frequency_label)

        # Device info:
        form = self._group(grid, "Device", 2, 0)
        self.info_labels = {
            key: QtWidgets.QLabel()
            for key in ["serial_number", "firmware_version", "hardware_version", "port"]
        }
        form.addRow("Serial number", self.info_labels["serial_number"])
        form.addRow("Firmware version", self.info_labels["firmware_version"])
        form.addRow("Hardware version", self.info_labels["hardware_version"])
        form.addRow("Port", self.info_labels["port"])

        # Notifications:
        form = self._group(grid, "Notifications", 2, 1)
        self.notify_trigger_out_checkbox = QtWidgets.QCheckBox()
        self.notify_trigger_out_checkbox.toggled.connect(self.notify_trigger_out_toggled)
        form.addRow("Notify on trigger out", self.notify_trigger_out_checkbox)
        self.notify_finished_checkbox = QtWidgets.QCheckBox()
        self.notify_finished_checkbox.toggled.connect(self.notify_finished_toggled)
        form.addRow("Notify when finished", self.notify_finished_checkbox)
        self.notifications_log = QtWidgets.QPlainTextEdit()
        self.notifications_log.setReadOnly(True)
        self.notifications_log.setMaximumBlockCount(1000)
        layout.addWidget(self.notifications_log)
        return widget

    def _button(self, icon, tooltip, slot, checkable=False):
        button = QtWidgets.QToolButton()
        button.setAutoRaise(True)
        button.setIcon(Icon(icon))
        button.setToolTip(tooltip)
        button.setCheckable(checkable)
        if checkable:
            button.toggled.connect(slot)
        else:
            button.clicked.connect(slot)
        return button

    def _group(self, grid, title, row, column):
        group = QtWidgets.QGroupBox(title)
        form = QtWidgets.QFormLayout(group)
        grid.addWidget(group, row, column)
        return form

    def initialise_workers(self):
        self.create_worker(
            "main_worker",
            "labscript_devices.NarwhalPulseGenerator.blacs_workers.NarwhalPulseGeneratorWorker",
            {"serial_number": self.connection_table_properties["serial_number"]},
        )
        self.primary_worker = "main_worker"

    def get_child_from_connection_table(self, parent_device_name, port):
        """Find the clockline or direct output on a channel."""
        if parent_device_name != self.device_name:
            return DeviceTab.get_child_from_connection_table(self, parent_device_name, port)
        device = self.connection_table.find_by_name(self.device_name)
        for pseudoclock in device.child_list.values():
            if pseudoclock.parent_port != "clock":
                continue
            for clockline in pseudoclock.child_list.values():
                if clockline.parent_port == port:
                    return clockline
                if clockline.parent_port == "internal":
                    for direct_outputs in clockline.child_list.values():
                        child = DeviceTab.get_child_from_connection_table(
                            self, direct_outputs.name, port
                        )
                        if child:
                            return child
        return None

    @define_state(MODE_MANUAL, True)
    def get_device_info(self):
        info = yield self.queue_work(self.primary_worker, "get_device_info")
        for key, label in self.info_labels.items():
            label.setText(str(info[key]))

    @define_state(MODE_MANUAL, True)
    def status_monitor(self):
        """Show the device state. Runs on a timer in manual mode and after each manual
        control."""
        state, powerline, run_time, notifications = yield self.queue_work(
            self.primary_worker, "get_status"
        )
        self._show_state(state, powerline, run_time)
        self._log_notifications(notifications)

    def _show_state(self, state, powerline, run_time):
        self._show_flag(self.running_label, state.running)
        self._show_flag(self.software_enable_label, state.software_run_enable)
        self._show_flag(self.hardware_enable_label, state.hardware_run_enable)
        self.current_address_label.setText(str(state.current_address))
        self.final_address_label.setText(str(state.final_address))
        seconds = run_time * CYCLE
        self.run_time_label.setText(f"{int(seconds // 60)} min {seconds % 60:.3f} s")
        self.clock_source_label.setText(state.clock_source)
        if powerline.locked:
            self.powerline_frequency_label.setText(f"{1 / (powerline.period * CYCLE):.3f} Hz")
        else:
            self.powerline_frequency_label.setText("no signal")
        # The widgets are set without their signals, which would send the values back
        # to the device, and a widget that is being edited is left alone.
        self._set(self.run_mode_combo.setCurrentText, state.run_mode, self.run_mode_combo)
        self._set(self.pause_button.setChecked, not state.software_run_enable, self.pause_button)
        self._set(
            self.accept_trigger_combo.setCurrentText,
            state.accept_hardware_trigger,
            self.accept_trigger_combo,
        )
        self._set(
            self.powerline_checkbox.setChecked, powerline.trigger_on_powerline, self.powerline_checkbox
        )
        self._set(
            self.powerline_delay_spinbox.setValue,
            powerline.trigger_delay * CYCLE * 1e3,
            self.powerline_delay_spinbox,
        )
        self._set(
            self.trigger_out_length_spinbox.setValue,
            state.trigger_out_length * CYCLE * 1e6,
            self.trigger_out_length_spinbox,
        )
        self._set(
            self.trigger_out_delay_spinbox.setValue,
            state.trigger_out_delay * CYCLE,
            self.trigger_out_delay_spinbox,
        )
        self._set(
            self.notify_trigger_out_checkbox.setChecked,
            state.notify_on_trigger_out,
            self.notify_trigger_out_checkbox,
        )
        self._set(
            self.notify_finished_checkbox.setChecked,
            state.notify_when_finished,
            self.notify_finished_checkbox,
        )

    @staticmethod
    def _set(setter, value, widget):
        if widget.hasFocus():
            return
        widget.blockSignals(True)
        try:
            setter(value)
        finally:
            widget.blockSignals(False)

    @staticmethod
    def _show_flag(label, value):
        icon = ":/qtutils/fugue/tick" if value else ":/qtutils/fugue/cross"
        label.setIcon(Icon(icon))

    def _log_notifications(self, notifications):
        if len(notifications) > 100:
            self.notifications_log.appendPlainText(
                f"{len(notifications)} notifications received"
            )
            return
        for notification in notifications:
            # The notification's timestamp is from time.monotonic():
            received = time.time() - (time.monotonic() - notification.timestamp)
            prefix = (
                f"{datetime.fromtimestamp(received):%H:%M:%S.%f} "
                f"(run time {notification.run_time * CYCLE:.7f} s):"
            )
            if notification.instruction:
                self.notifications_log.appendPlainText(
                    f"{prefix} instruction {notification.address} started"
                )
            if notification.trigger_out:
                self.notifications_log.appendPlainText(f"{prefix} trigger out")
            if notification.finished:
                self.notifications_log.appendPlainText(f"{prefix} run finished")

    # Buffered mode:

    @define_state(MODE_BUFFERED, True)
    def start_run(self, notify_queue):
        """Start the shot; `wait_for_run_finished` puts 'done' in `notify_queue` when
        the device reports that the run has finished."""
        self.notify_queue = notify_queue
        yield self.queue_work(self.primary_worker, "start_run")
        self.wait_for_run_finished()

    @define_state(MODE_BUFFERED, False)
    def wait_for_run_finished(self):
        """Wait in the worker for the run to finish, in chunks of at most
        RUN_FINISHED_WAIT_CHUNK seconds so that an abort can be processed between
        them. A queued call is discarded when the tab leaves buffered mode."""
        finished, notifications = yield self.queue_work(
            self.primary_worker, "wait_for_run_finished", self.RUN_FINISHED_WAIT_CHUNK
        )
        self._log_notifications(notifications)
        if finished:
            if self.notify_queue is not None:
                self.notify_queue.put("done")
                self.notify_queue = None
        else:
            self.wait_for_run_finished()

    # Manual controls:

    @define_state(MODE_MANUAL, True)
    def start(self, widget=None):
        yield self.queue_work(self.primary_worker, "software_trigger")
        self.status_monitor()

    @define_state(MODE_MANUAL, True)
    def pause(self, checked, widget=None):
        yield self.queue_work(self.primary_worker, "set_options", software_run_enable=not checked)
        self.status_monitor()

    @define_state(MODE_MANUAL, True)
    def stop(self, widget=None):
        yield self.queue_work(self.primary_worker, "disable_after_current_run")
        self.status_monitor()

    @define_state(MODE_MANUAL, True)
    def reset(self, widget=None):
        yield self.queue_work(self.primary_worker, "reset_run")
        self.status_monitor()

    @define_state(MODE_MANUAL, True)
    def run_mode_changed(self, run_mode):
        yield self.queue_work(self.primary_worker, "set_options", run_mode=run_mode)

    @define_state(MODE_MANUAL, True)
    def accept_trigger_changed(self, accept_hardware_trigger):
        yield self.queue_work(
            self.primary_worker, "set_options", accept_hardware_trigger=accept_hardware_trigger
        )

    @define_state(MODE_MANUAL, True)
    def trigger_on_powerline_toggled(self, checked):
        yield self.queue_work(
            self.primary_worker, "set_powerline_options", trigger_on_powerline=checked
        )

    @define_state(MODE_MANUAL, True)
    def powerline_delay_changed(self):
        cycles = int(round(self.powerline_delay_spinbox.value() * 1e-3 / CYCLE))
        yield self.queue_work(self.primary_worker, "set_powerline_options", trigger_delay=cycles)

    @define_state(MODE_MANUAL, True)
    def trigger_out_length_changed(self):
        cycles = int(round(self.trigger_out_length_spinbox.value() * 1e-6 / CYCLE))
        yield self.queue_work(self.primary_worker, "set_options", trigger_out_length=cycles)

    @define_state(MODE_MANUAL, True)
    def trigger_out_delay_changed(self):
        cycles = int(round(self.trigger_out_delay_spinbox.value() / CYCLE))
        yield self.queue_work(self.primary_worker, "set_options", trigger_out_delay=cycles)

    @define_state(MODE_MANUAL, True)
    def notify_trigger_out_toggled(self, checked):
        yield self.queue_work(self.primary_worker, "set_options", notify_on_trigger_out=checked)

    @define_state(MODE_MANUAL, True)
    def notify_finished_toggled(self, checked):
        yield self.queue_work(self.primary_worker, "set_options", notify_when_finished=checked)
