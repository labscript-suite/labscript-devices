#####################################################################
#                                                                   #
# /labscript_devices/NarwhalPulseGenerator/blacs_workers.py         #
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
import queue
import time

import labscript_utils.h5_lock  # noqa: F401
import h5py
import numpy as np
import zprocess
from blacs.tab_base_classes import Worker
from labscript_utils.connections import _ensure_str
import labscript_utils.properties as properties

from . import driver
from .driver import CYCLE, INSTRUCTION_DTYPE, drain, firmware_string
from .labscript_devices import N_CHANNELS


def pack_values(values):
    """The 24-bit state for a dictionary of front panel values."""
    return sum(1 << n for n in range(N_CHANNELS) if values[f"channel {n}"])


def unpack_state(state):
    """The front panel values for a 24-bit state."""
    return {f"channel {n}": int((state >> n) & 1) for n in range(N_CHANNELS)}


class NarwhalPulseGeneratorWorker(Worker):
    """Operates one pulse generator.

    During a run the worker blocks on the device's notifications instead of polling
    its state. As the master pseudoclock and wait monitor, it measures each wait from
    the notifications of the instruction that waits and of the instruction after it,
    and resumes the device with a software trigger when a wait times out.
    """

    def init(self):
        self.device = self._connect()
        info = self.device.info
        self.device_info = {
            "serial_number": info.serial_number,
            "firmware_version": firmware_string(info.firmware_version),
            "hardware_version": info.hardware_version,
            "port": self.device.port,
        }
        self.logger.info(
            f"Connected to pulse generator {info.serial_number} on {self.device.port}, "
            f"hardware version {info.hardware_version}, firmware "
            f"{firmware_string(info.firmware_version)}"
        )
        # The device's settings are left as they are, so that restarting BLACS does not
        # disturb a run in progress.
        self.all_waits_finished = zprocess.Event("all_waits_finished", role="post")
        self.wait_durations_analysed = zprocess.Event(
            "wait_durations_analysed", role="post"
        )
        self.wait_completed = zprocess.Event("wait_completed", role="post")
        self.h5_file = None
        self.is_master = False
        self.stop_time = None
        self.final_address = None
        #: The `waits` dataset of the shot if this device is the wait monitor.
        self.wait_table = None
        self.wait_addresses = []
        self.wait_durations = []
        self._reset_run_state()

    def _connect(self):
        return driver.connect(self.serial_number)

    def _reset_run_state(self):
        drain(self.device.notifications)
        self.run_finished = False
        #: `time.monotonic()` at the software trigger.
        self.trigger_time = None
        #: The number of waits that have ended.
        self.current_wait = 0
        #: Run time of the device in cycles at which the current wait began, or None
        #: if the device is not waiting.
        self.wait_start = None
        #: `time.monotonic()` at which the current wait times out.
        self.wait_deadline = None
        self.wait_timed_out = False

    def shutdown(self):
        self.device.close()

    def get_device_info(self):
        return self.device_info

    def program_manual(self, values):
        self.device.set_static_state(pack_values(values))
        self.device.raise_errors()
        return {}

    def check_remote_values(self):
        return unpack_state(self.device.get_state().state)

    def get_status(self):
        """The device state, the powerline state, the run time in cycles and the
        notifications received since the last call."""
        state = self.device.get_state()
        powerline = self.device.get_powerline_state()
        run_time = self.device.get_run_time()
        notifications = drain(self.device.notifications)
        self.device.raise_errors()
        return state, powerline, run_time, notifications

    # Manual controls of the tab:

    def software_trigger(self):
        self.device.trigger()
        self.device.raise_errors()

    def disable_after_current_run(self):
        self.device.disable_after_current_run()
        self.device.raise_errors()

    def reset_run(self):
        self.device.set_options(accept_hardware_trigger="never")
        self.device.reset_run()
        self.device.raise_errors()

    def set_options(self, **options):
        """Set device options; see `driver.encode_options`."""
        self.device.set_options(**options)
        self.device.raise_errors()

    def set_powerline_options(self, **options):
        """Set powerline options; see `driver.encode_powerline_options`."""
        self.device.set_powerline_options(**options)
        self.device.raise_errors()

    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):
        self.h5_file = h5file
        with h5py.File(h5file, "r") as f:
            program = f[f"devices/{device_name}/PULSE_PROGRAM"][:]
            props = properties.get(f, device_name, "device_properties")
            waits = f["waits"]
            monitor = f"{device_name}_internal_wait_monitor_outputs"
            is_wait_monitor = (
                len(waits) > 0
                and _ensure_str(waits.attrs["wait_monitor_acquisition_device"]) == monitor
                and _ensure_str(waits.attrs["wait_monitor_timeout_device"]) == monitor
            )
            self.wait_table = waits[:] if is_wait_monitor else None
        self.is_master = bool(props["is_master_pseudoclock"])
        self.stop_time = float(props["stop_time"]) if self.is_master else None
        self.final_address = len(program) - 1

        # Channels that the shot does not use keep their front panel values, as does
        # every channel during the one-cycle instruction of a wait at t=0.
        front_panel = pack_values(initial_values)
        used = int(props["used_channels"])
        instructions = np.zeros(len(program), dtype=INSTRUCTION_DTYPE)
        instructions["address"] = np.arange(len(program))
        instructions["state"] = (program["state"] & used) | (front_panel & ~used & 0xFFFFFF)
        if props["wait_at_start"]:
            instructions["state"][0] = front_panel
        for name in ["duration", "goto_address", "goto_counter", "stop_and_wait", "powerline_sync"]:
            instructions[name] = program[name]
        # A wait is measured from the notifications of the instruction that waits and
        # of the instruction after it.
        waiting = program["stop_and_wait"]
        instructions["notify"] = waiting | np.concatenate([[False], waiting[:-1]])
        self.wait_addresses = np.flatnonzero(waiting).tolist()
        self.wait_durations = program["duration"][waiting].tolist()
        if self.wait_table is not None:
            if len(self.wait_addresses) != len(self.wait_table):
                raise RuntimeError(
                    f"{device_name} has {len(self.wait_addresses)} instructions that "
                    f"wait, but the shot has {len(self.wait_table)} waits."
                )
            self.measured_waits = np.zeros(len(self.wait_table))
            self.wait_timeouts = np.zeros(len(self.wait_table), dtype=bool)

        device = self.device
        device.set_options(accept_hardware_trigger="never", software_run_enable=False)
        device.reset_run()
        device.write_instructions(instructions)
        trigger_on_powerline = bool(props["trigger_on_powerline"])
        device.set_powerline_options(
            trigger_on_powerline=trigger_on_powerline,
            trigger_delay=int(props["powerline_trigger_delay"]),
        )
        if trigger_on_powerline and not device.get_powerline_state().locked:
            raise RuntimeError(
                f"{device_name} is set to trigger on the powerline, but has no "
                "powerline signal."
            )
        # The master accepts hardware triggers so that one can end a wait, but
        # software_run_enable gates them until the software trigger of start_run, which
        # sets it. A secondary device is armed and starts on its hardware trigger.
        device.set_options(
            final_address=self.final_address,
            run_mode="single",
            accept_hardware_trigger="single_run",
            trigger_out_length=int(props["trigger_out_length"]),
            trigger_out_delay=int(props["trigger_out_delay"]),
            notify_on_trigger_out=False,
            notify_when_finished=True,
            software_run_enable=not self.is_master,
        )
        device.raise_errors()
        self._reset_run_state()
        return unpack_state(int(instructions["state"][-1]))

    def start_run(self):
        self._reset_run_state()
        self.trigger_time = time.monotonic()
        self.device.trigger()

    def wait_for_run_finished(self, timeout):
        """Block until the device reports that the run has finished or `timeout`
        seconds have passed, processing the notifications that arrive. Returns whether
        the run has finished and the notifications received.

        The tab calls this repeatedly. When the expected end of the shot is within
        `timeout` of this call's deadline, the deadline is extended past the expected
        end, so that the finish does not fall in the gap between two calls."""
        now = time.monotonic()
        deadline = now + timeout
        if self.stop_time is not None and self.trigger_time is not None:
            expected_end = self.trigger_time + self.stop_time
            if expected_end - timeout <= deadline <= expected_end + timeout:
                deadline = expected_end + timeout
        notifications = []
        while not self.run_finished:
            remaining = deadline - time.monotonic()
            if self.wait_deadline is not None:
                remaining = min(remaining, self.wait_deadline - time.monotonic())
            try:
                notification = self.device.notifications.get(timeout=max(remaining, 0))
            except queue.Empty:
                pass
            else:
                notifications.append(notification)
                self._process_notification(notification)
            self._check_wait_timeout()
            if time.monotonic() >= deadline:
                break
        self.device.raise_errors()
        return self.run_finished, notifications

    def _process_notification(self, notification):
        if notification.finished:
            self.run_finished = True
        if not notification.instruction or self.wait_table is None:
            return
        # The instruction after a wait can be the instruction of the next wait, so the
        # end of one wait is checked before the start of the next.
        if (
            self.wait_start is not None
            and notification.address == self.wait_addresses[self.current_wait] + 1
        ):
            self.measured_waits[self.current_wait] = (
                notification.run_time - self.wait_start
            ) * CYCLE
            self.wait_timeouts[self.current_wait] = self.wait_timed_out
            self.wait_completed.post(
                self.h5_file,
                data=_ensure_str(self.wait_table[self.current_wait]["label"]),
            )
            self.current_wait += 1
            self.wait_start = None
            self.wait_deadline = None
            if self.current_wait == len(self.wait_table):
                self.all_waits_finished.post(self.h5_file)
        if (
            self.current_wait < len(self.wait_addresses)
            and notification.address == self.wait_addresses[self.current_wait]
        ):
            duration = self.wait_durations[self.current_wait]
            self.wait_start = notification.run_time + duration
            self.wait_deadline = (
                notification.timestamp
                + duration * CYCLE
                + float(self.wait_table[self.current_wait]["timeout"])
            )
            self.wait_timed_out = False

    def _check_wait_timeout(self):
        """Resume the device with a software trigger if its wait has timed out."""
        if self.wait_deadline is None or time.monotonic() < self.wait_deadline:
            return
        self.wait_deadline = None
        state = self.device.get_state()
        if (
            not state.running
            and state.current_address == self.wait_addresses[self.current_wait]
        ):
            self.wait_timed_out = True
            self.device.trigger()

    def transition_to_manual(self):
        if self.wait_table is not None:
            with h5py.File(self.h5_file, "a") as f:
                dtypes = [
                    ("label", "S256"),
                    ("time", float),
                    ("timeout", float),
                    ("duration", float),
                    ("timed_out", bool),
                ]
                data = np.empty(len(self.wait_table), dtype=dtypes)
                data["label"] = self.wait_table["label"]
                data["time"] = self.wait_table["time"]
                data["timeout"] = self.wait_table["timeout"]
                data["duration"] = self.measured_waits
                data["timed_out"] = self.wait_timeouts
                f.create_dataset("/data/waits", data=data)
            self.wait_durations_analysed.post(self.h5_file)

        # A secondary device may finish a little after the master.
        deadline = time.monotonic() + 2.0
        while True:
            state = self.device.get_state()
            if not state.running and state.current_address == self.final_address:
                break
            if time.monotonic() > deadline:
                hint = "" if self.is_master else " It may not have received its trigger."
                raise RuntimeError(
                    f"{self.device_name} is at instruction {state.current_address} of "
                    f"{self.final_address} and {'is' if state.running else 'is not'} "
                    f"running.{hint}"
                )
            time.sleep(0.01)
        self.device.set_options(accept_hardware_trigger="never")
        self.device.raise_errors()
        return True

    def abort_buffered(self):
        self.device.set_options(accept_hardware_trigger="never")
        self.device.reset_run()
        self.device.raise_errors()
        return True

    def abort_transition_to_buffered(self):
        return self.abort_buffered()
