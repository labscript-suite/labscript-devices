#####################################################################
#                                                                   #
# /NI_DAQmx/blacs_workers.py                                        #
#                                                                   #
# Copyright 2018, Monash University, JQI, Christopher Billington    #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################
import sys
import time
import threading
import socket
from collections import deque
from PyDAQmx import *
from PyDAQmx.DAQmxConstants import *
from PyDAQmx.DAQmxTypes import *
from PyDAQmx.DAQmxCallBack import *

import numpy as np
from numpy.lib.recfunctions import structured_to_unstructured
import labscript_utils.h5_lock
import h5py
from zprocess import Event
from zprocess.utils import _reraise

import labscript_utils.properties as properties
from labscript_utils import dedent
from labscript_utils.connections import _ensure_str

from blacs.tab_base_classes import Worker

from .utils import split_conn_port, split_conn_DO, split_conn_AI, split_conn_CI
from .daqmx_utils import incomplete_sample_detection

import json
from pathlib import Path

import PyDAQmx

from pythonlib.data_saver import DataSaver
from pythonlib.online_monitor import OnlineMonitor


class NI_DAQmxOutputWorker(Worker):
    def _reserved_lines_by_port(self):
        lines_by_port = {}
        for connection in getattr(self, 'counter_reserved_dio_lines', []):
            port, line = split_conn_DO(connection)
            port_str = 'port%d' % port
            lines_by_port.setdefault(port_str, set()).add(line)
        return lines_by_port

    def _do_channel_lines(self, port_str):
        reserved = self._reserved_lines_by_port().get(port_str, set())
        return [
            line
            for line in range(self.ports[port_str]['num_lines'])
            if line not in reserved
        ]

    def _create_DO_channel(self, port_str):
        lines = self._do_channel_lines(port_str)
        if not lines:
            return lines
        if len(lines) == self.ports[port_str]['num_lines']:
            con = '%s/%s' % (self.MAX_name, port_str)
        else:
            con = ','.join(
                '%s/%s/line%d' % (self.MAX_name, port_str, line)
                for line in lines
            )
        self.DO_task.CreateDOChan(con, "", DAQmx_Val_ChanForAllLines)
        return lines

    def _compact_DO_data(self, DO_table, ports, channel_lines_by_port):
        data = np.zeros((len(DO_table), len(ports)), dtype=np.uint32)
        for i, port_str in enumerate(ports):
            physical_values = DO_table[port_str].astype(np.uint32)
            compact_values = np.zeros(len(DO_table), dtype=np.uint32)
            for compact_bit, physical_line in enumerate(channel_lines_by_port[port_str]):
                bit_values = (physical_values >> physical_line) & 1
                compact_values |= bit_values << compact_bit
            data[:, i] = compact_values
        return np.ascontiguousarray(data)

    def init(self):
        self.check_version()
        # Reset Device: clears previously added routes etc. Note: is insufficient for
        # some devices, which require power cycling to truly reset.
        DAQmxResetDevice(self.MAX_name) #TODO
        self.start_manual_mode_tasks()

    def stop_tasks(self):
        if self.AO_task is not None:
            self.AO_task.StopTask()
            self.AO_task.ClearTask()
            self.AO_task = None
        if self.DO_task is not None:
            self.DO_task.StopTask()
            self.DO_task.ClearTask()
            self.DO_task = None

    def shutdown(self):
        self.stop_tasks()

    def check_version(self):
        """Check the version of PyDAQmx is high enough to avoid a known bug"""
        major = uInt32()
        minor = uInt32()
        patch = uInt32()
        DAQmxGetSysNIDAQMajorVersion(major)
        DAQmxGetSysNIDAQMinorVersion(minor)
        DAQmxGetSysNIDAQUpdateVersion(patch)

        if major.value == 14 and minor.value < 2:
            msg = """There is a known bug with buffered shots using NI DAQmx v14.0.0.
                This bug does not exist on v14.2.0. You are currently using v%d.%d.%d.
                Please ensure you upgrade to v14.2.0 or higher."""
            raise Exception(dedent(msg) % (major.value, minor.value, patch.value))

    def start_manual_mode_tasks(self):
        # Create tasks:
        if self.num_AO > 0:
            self.AO_task = Task()
        else:
            self.AO_task = None

        if self.ports and self.DO_hardware_names:
            self.DO_task = Task()
        else:
            self.DO_task = None

        # Setup AO channels
        for i in range(self.num_AO):
            con = self.MAX_name + "/ao%d" % i
            self.AO_task.CreateAOVoltageChan(
                con, "", self.Vmin, self.Vmax, DAQmx_Val_Volts, None
            )

        # Setup DO channels
        self.manual_DO_ports = []
        self.manual_DO_channel_lines = {}
        for port_str in sorted(self.ports, key=split_conn_port):
            if not self.ports[port_str]['num_lines'] or self.DO_task is None:
                continue
            lines = self._create_DO_channel(port_str)
            if lines:
                self.manual_DO_ports.append(port_str)
                self.manual_DO_channel_lines[port_str] = lines

        # Start tasks:
        if self.AO_task is not None:
            self.AO_task.StartTask()
        if self.DO_task is not None:
            self.DO_task.StartTask()

    def program_manual(self, front_panel_values):
        written = int32()
        if self.AO_task is not None:
            AO_data = np.zeros(self.num_AO, dtype=np.float64)
            for i in range(self.num_AO):
                AO_data[i] = front_panel_values['ao%d' % i]
            self.AO_task.WriteAnalogF64(
                1, True, 1, DAQmx_Val_GroupByChannel, AO_data, written, None
            )
        if self.DO_task is not None:
            # Due to two bugs in DAQmx, we will always pack our data into a uint32 and
            # write using WriteDigitalU32. The first bug is some kind of use of
            # uninitialised memory when using WriteDigitalLines, discussed here:
            # https://bitbucket.org/labscript_suite
            #     /labscript_devices/pull-requests/56/#comment-83671312
            # The second is that using a smaller int dtype sometimes fails even though
            # it is the correct int size for the size of the port. Using a 32 bit int
            # always works, the additional bits are ignored. This is discussed here:
            # https://forums.ni.com/t5/Multifunction-DAQ
            #     /problem-with-correlated-DIO-on-USB-6341/td-p/3344066
            DO_data = np.zeros((1, len(self.manual_DO_ports)), dtype=np.uint32)
            for conn, value in front_panel_values.items():
                if conn.startswith('port'):
                    port, line = split_conn_DO(conn)
                    port_str = 'port%d' % port
                    if port_str not in self.manual_DO_channel_lines:
                        continue
                    if line not in self.manual_DO_channel_lines[port_str]:
                        continue
                    compact_line = self.manual_DO_channel_lines[port_str].index(line)
                    port_index = self.manual_DO_ports.index(port_str)
                    DO_data[0, port_index] |= value << compact_line
            self.DO_task.WriteDigitalU32(
                1, True, 10.0, DAQmx_Val_GroupByScanNumber, DO_data, written, None
            )
        # TODO: return coerced/quantised values
        return {}

    def get_output_tables(self, h5file, device_name):
        """Return the AO and DO tables rom the file, or None if they do not exist."""
        with h5py.File(h5file, 'r') as hdf5_file:
            group = hdf5_file['devices'][device_name]
            try:
                AO_table = group['AO'][:]
            except KeyError:
                AO_table = None
            try:
                DO_table = group['DO'][:]
            except KeyError:
                DO_table = None
        return AO_table, DO_table

    def set_mirror_clock_terminal_connected(self, connected):
        """Mirror the clock terminal on another terminal to allow daisy chaining of the
        clock line to other devices, if applicable"""
        if self.clock_mirror_terminal is None:
            return
        if connected:
            DAQmxConnectTerms(
                self.clock_terminal,
                self.clock_mirror_terminal,
                DAQmx_Val_DoNotInvertPolarity,
            )
        else:
            DAQmxDisconnectTerms(self.clock_terminal, self.clock_mirror_terminal)

    def set_connected_terminals_connected(self, connected):
        """Connect the terminals in the connected terminals list.
        Allows on daisy chaining of the clock line to/from other devices
        that do not have a direct route (see Device Routes in NI MAX)."""
        if self.connected_terminals is None:
            return
        if connected:
            for terminal_pair in self.connected_terminals:
                DAQmxConnectTerms(
                    terminal_pair[0],
                    terminal_pair[1],
                    DAQmx_Val_DoNotInvertPolarity,
                )
        else:
            for terminal_pair in self.connected_terminals:
                DAQmxDisconnectTerms(terminal_pair[0], terminal_pair[1])

    def program_buffered_DO(self, DO_table):
        """Create the DO task and program in the DO table for a shot. Return a
        dictionary of the final values of each channel in use"""
        if DO_table is None:
            return {}
        self.DO_task = Task()
        written = int32()
        ports = DO_table.dtype.names

        final_values = {}
        channel_lines_by_port = {}
        for port_str in ports:
            # Add each port to the task:
            channel_lines = self._create_DO_channel(port_str)
            channel_lines_by_port[port_str] = channel_lines

            # Collect the final values of the lines on this port:
            port_final_value = DO_table[port_str][-1]
            for line in channel_lines:
                # Extract each digital value from the packed bits:
                line_final_value = bool((1 << line) & port_final_value)
                final_values['%s/line%d' % (port_str, line)] = int(line_final_value)

        DO_table = self._compact_DO_data(DO_table, ports, channel_lines_by_port)

        # Check if DOs are all zero for the whole shot. If they are this triggers a
        # bug in NI-DAQmx that throws a cryptic error for buffered output. In this
        # case, run it as a non-buffered task.
        self.DO_all_zero = not np.any(DO_table)
        if self.DO_all_zero:
            DO_table = DO_table[0:1]

        if self.static_DO or self.DO_all_zero:
            # Static DO. Start the task and write data, no timing configuration.
            self.DO_task.StartTask()
            # Write data. See the comment in self.program_manual as to why we are using
            # uint32 instead of the native size of each port
            self.DO_task.WriteDigitalU32(
                1,  # npts
                False,  # autostart
                10.0,  # timeout
                DAQmx_Val_GroupByScanNumber,
                DO_table,
                written,
                None,
            )
        else:
            # We use all but the last sample (which is identical to the second last
            # sample) in order to ensure there is one more clock tick than there are
            # samples. This is required by some devices to determine that the task has
            # completed.
            npts = len(DO_table) - 1

            # Set up timing:
            self.DO_task.CfgSampClkTiming(
                self.clock_terminal,
                self.clock_limit,
                DAQmx_Val_Rising,
                DAQmx_Val_FiniteSamps,
                npts,
            )

            # Write data. See the comment in self.program_manual as to why we are using
            # uint32 instead of the native size of each port.
            self.DO_task.WriteDigitalU32(
                npts,
                False,  # autostart
                10.0,  # timeout
                DAQmx_Val_GroupByScanNumber,
                DO_table[:-1], # All but the last sample as mentioned above
                written,
                None,
            )

            # Go!
            self.DO_task.StartTask()

        return final_values

    def program_buffered_AO(self, AO_table):
        if AO_table is None:
            return {}
        self.AO_task = Task()
        written = int32()
        channels = ', '.join(self.MAX_name + '/' + c for c in AO_table.dtype.names)
        self.AO_task.CreateAOVoltageChan(
            channels, "", self.Vmin, self.Vmax, DAQmx_Val_Volts, None
        )

        # Collect the final values of the analog outs:
        final_values = dict(zip(AO_table.dtype.names, AO_table[-1]))

        # Convert AO table to a regular array and ensure it is C continguous:
        AO_table = np.ascontiguousarray(
            structured_to_unstructured(AO_table, dtype=np.float64)
        )

        # Check if AOs are all zero for the whole shot. If they are this triggers a
        # bug in NI-DAQmx that throws a cryptic error for buffered output. In this
        # case, run it as a non-buffered task.
        self.AO_all_zero = not np.any(AO_table)
        if self.AO_all_zero:
            AO_table = AO_table[0:1]

        if self.static_AO or self.AO_all_zero:
            # Static AO. Start the task and write data, no timing configuration.
            self.AO_task.StartTask()
            self.AO_task.WriteAnalogF64(
                1, True, 10.0, DAQmx_Val_GroupByChannel, AO_table, written, None
            )
        else:
            # We use all but the last sample (which is identical to the second last
            # sample) in order to ensure there is one more clock tick than there are
            # samples. This is required by some devices to determine that the task has
            # completed.
            npts = len(AO_table) - 1

            # Set up timing:
            self.AO_task.CfgSampClkTiming(
                self.clock_terminal,
                self.clock_limit,
                DAQmx_Val_Rising,
                DAQmx_Val_FiniteSamps,
                npts,
            )

            # Write data:
            self.AO_task.WriteAnalogF64(
                npts,
                False,  # autostart
                10.0,  # timeout
                DAQmx_Val_GroupByScanNumber,
                AO_table[:-1],  # All but the last sample as mentioned above
                written,
                None,
            )

            # Go!
            self.AO_task.StartTask()

        return final_values

    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):
        # Store the initial values in case we have to abort and restore them:
        self.initial_values = initial_values

        # Stop the manual mode output tasks, if any:
        self.stop_tasks()

        # Get the data to be programmed into the output tasks:
        AO_table, DO_table = self.get_output_tables(h5file, device_name)

        # Mirror the clock terminal, if applicable:
        self.set_mirror_clock_terminal_connected(True)

        # Mirror other terminals, if applicable
        self.set_connected_terminals_connected(True)

        # Program the output tasks and retrieve the final values of each output:
        DO_final_values = self.program_buffered_DO(DO_table)
        AO_final_values = self.program_buffered_AO(AO_table)

        final_values = {}
        final_values.update(DO_final_values)
        final_values.update(AO_final_values)

        # If we are the wait timeout device, then the final value of the timeout line
        # should be its rearm value:
        if self.wait_timeout_device == self.device_name:
            final_values[self.wait_timeout_connection] = self.wait_timeout_rearm_value

        return final_values

    def transition_to_manual(self, abort=False):
        # Stop output tasks and call program_manual. Only call StopTask if not aborting.
        # Otherwise results in an error if output was incomplete. If aborting, call
        # ClearTask only.
        npts = uInt64()
        samples = uInt64()
        tasks = []
        if self.AO_task is not None:
            tasks.append([self.AO_task, self.static_AO or self.AO_all_zero, 'AO'])
            self.AO_task = None
        if self.DO_task is not None:
            tasks.append([self.DO_task, self.static_DO or self.DO_all_zero, 'DO'])
            self.DO_task = None

        for task, static, name in tasks:
            if not abort:
                if not static:
                    try:
                        # Wait for task completion with a 1 second timeout:
                        task.WaitUntilTaskDone(1)
                    finally:
                        # Log where we were up to in sample generation, regardless of
                        # whether the above succeeded:
                        task.GetWriteCurrWritePos(npts)
                        task.GetWriteTotalSampPerChanGenerated(samples)
                        # Detect -1 even though they're supposed to be unsigned ints, -1
                        # seems to indicate the task was not started:
                        current = samples.value if samples.value != 2 ** 64 - 1 else -1
                        total = npts.value if npts.value != 2 ** 64 - 1 else -1
                        msg = 'Stopping %s at sample %d of %d'
                        self.logger.info(msg, name, current, total)
                task.StopTask()
            task.ClearTask()

        # Remove the mirroring of the clock terminal, if applicable:
        self.set_mirror_clock_terminal_connected(False)

        # Remove connections between other terminals, if applicable:
        self.set_connected_terminals_connected(False)

        # Set up manual mode tasks again:
        self.start_manual_mode_tasks()
        if abort:
            # Reprogram the initial states:
            self.program_manual(self.initial_values)

        return True

    def abort_transition_to_buffered(self):
        return self.transition_to_manual(True)

    def abort_buffered(self):
        return self.transition_to_manual(True)


class NI_DAQmxAcquisitionWorker(Worker):
    MAX_READ_INTERVAL = 0.2
    MAX_READ_PTS = 10000

    def init(self):
        # Prevent interference between the read callback and the shutdown code:
        self.tasklock = threading.RLock()

        # Assigned on a per-task basis and cleared afterward:
        self.read_array = None
        self.task = None

        # Assigned on a per-shot basis and cleared afterward:
        self.buffered_mode = False
        self.h5_file = None
        self.acquired_data = None
        self.buffered_rate = None
        self.buffered_chans = None

        # Hard coded for now. Perhaps we will add functionality to enable
        # and disable inputs in manual mode, and adjust the rate:
        self.manual_mode_chans = self.AI_chans
        self.manual_mode_rate = 1000

        # An event for knowing when the wait durations are known, so that we may use
        # them to chunk up acquisition data:
        self.wait_durations_analysed = Event('wait_durations_analysed')

        # Start task for manual mode
        self.start_task(self.manual_mode_chans, self.manual_mode_rate)

    def shutdown(self):
        if self.task is not None:
            self.stop_task()

    def read(self, task_handle, event_type, num_samples, callback_data=None):
        """Called as a callback by DAQmx while task is running. Also called by us to get
        remaining data just prior to stopping the task. Since the callback runs
        in a separate thread, we need to serialise access to instance variables"""
        samples_read = int32()
        with self.tasklock:
            if self.task is None or task_handle != self.task.taskHandle.value:
                # Task stopped already.
                return 0
            self.task.ReadAnalogF64(
                num_samples,
                -1,
                DAQmx_Val_GroupByScanNumber,
                self.read_array,
                self.read_array.size,
                samples_read,
                None,
            )
            # Select only the data read, and downconvert to 32 bit:
            data = self.read_array[: int(samples_read.value), :].astype(np.float32)
            if self.buffered_mode:
                # Append to the list of acquired data:
                self.acquired_data.append(data)
            else:
                # TODO: Send it to the broker thingy.
                pass
        return 0

    def start_task(self, chans, rate):
        """Set up a task that acquires data with a callback every MAX_READ_PTS points or
        MAX_READ_INTERVAL seconds, whichever is faster. NI DAQmx calls callbacks in a
        separate thread, so this method returns, but data acquisition continues until
        stop_task() is called. Data is appended to self.acquired_data if
        self.buffered_mode=True, or (TODO) sent to the [whatever the AI server broker is
        called] if self.buffered_mode=False."""

        if self.task is not None:
            raise RuntimeError('Task already running')

        if chans is None:
            return

        # Get data MAX_READ_PTS points at a time or once every MAX_READ_INTERVAL
        # seconds, whichever is faster:
        num_samples = min(self.MAX_READ_PTS, int(rate * self.MAX_READ_INTERVAL))

        self.read_array = np.zeros((num_samples, len(chans)), dtype=np.float64)
        self.task = Task()

        if self.AI_term == 'RSE':
            term = DAQmx_Val_RSE
        elif self.AI_term == 'NRSE':
            term = DAQmx_Val_NRSE
        elif self.AI_term == 'Diff':
            term = DAQmx_Val_Diff
        elif self.AI_term == 'PseudoDiff':
            term = DAQmx_Val_PseudoDiff

        for chan in chans:
            self.task.CreateAIVoltageChan(
                self.MAX_name + '/' + chan,
                "",
                term,
                self.AI_range[0],
                self.AI_range[1],
                DAQmx_Val_Volts,
                None,
            )

        if self.AI_timebase_terminal is None:
            # use internal default
            pass
        else:
            self.task.SetSampClkTimebaseSrc(self.AI_timebase_terminal)
            self.task.SetSampClkTimebaseRate(self.AI_timebase_rate)

        self.task.CfgSampClkTiming(
            "", rate, DAQmx_Val_Rising, DAQmx_Val_ContSamps, num_samples
        )
        if self.buffered_mode:
            self.task.CfgDigEdgeStartTrig(self.clock_terminal, DAQmx_Val_Rising)

        # This must not be garbage collected until the task is:
        self.task.callback_ptr = DAQmxEveryNSamplesEventCallbackPtr(self.read)

        self.task.RegisterEveryNSamplesEvent(
            DAQmx_Val_Acquired_Into_Buffer, num_samples, 0, self.task.callback_ptr, 100
        )

        self.task.StartTask()

    def stop_task(self):
        with self.tasklock:
            if self.task is None:
                raise RuntimeError('Task not running')
            # Read remaining data:
            self.read(self.task, None, -1)
            # Stop the task:
            self.task.StopTask()
            self.task.ClearTask()
            self.task = None
            self.read_array = None

    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):
        self.logger.debug('transition_to_buffered')

        # read channels, acquisition rate, etc from H5 file
        with h5py.File(h5file, 'r') as f:
            group = f['/devices/' + device_name]
            if 'AI' not in group:
                # No acquisition
                return {}
            AI_table = group['AI'][:]
            device_properties = properties.get(f, device_name, 'device_properties')

        chans = [_ensure_str(c) for c in AI_table['connection']]
        # Remove duplicates and sort:
        if chans:
            self.buffered_chans = sorted(set(chans), key=split_conn_AI)
        self.h5_file = h5file
        self.buffered_rate = device_properties['acquisition_rate']
        if device_properties['start_delay_ticks']:
            # delay is defined in sample clock ticks, calculate in sec and save for later
            self.AI_start_delay = self.AI_start_delay_ticks*self.buffered_rate
        self.acquired_data = []
        # Stop the manual mode task and start the buffered mode task:
        self.stop_task()
        self.buffered_mode = True
        self.start_task(self.buffered_chans, self.buffered_rate)
        return {}

    def transition_to_manual(self, abort=False):
        self.logger.debug('transition_to_manual')
        #  If we were doing buffered mode acquisition, stop the buffered mode task and
        # start the manual mode task. We might not have been doing buffered mode
        # acquisition if abort() was called when we are not in buffered mode, or if
        # there were no acuisitions this shot.
        if not self.buffered_mode:
            return True
        if self.buffered_chans is not None:
            self.stop_task()
        self.buffered_mode = False
        self.logger.info('transitioning to manual mode, task stopped')
        self.start_task(self.manual_mode_chans, self.manual_mode_rate)

        if abort:
            self.acquired_data = None
            self.buffered_chans = None
            self.h5_file = None
            self.buffered_rate = None
            return True

        with h5py.File(self.h5_file, 'a') as hdf5_file:
            data_group = hdf5_file['data']
            data_group.create_group(self.device_name)
            waits_in_use = len(hdf5_file['waits']) > 0

        if self.buffered_chans is not None and not self.acquired_data:
            msg = """No data was acquired. Perhaps the acquisition task was not
                triggered to start, is the device connected to a pseudoclock?"""
            raise RuntimeError(dedent(msg))
        # Concatenate our chunks of acquired data and recast them as a structured
        # array with channel names:
        if self.acquired_data:
            start_time = time.time()
            dtypes = [(chan, np.float32) for chan in self.buffered_chans]
            raw_data = np.concatenate(self.acquired_data).view(dtypes)
            raw_data = raw_data.reshape((len(raw_data),))
            self.acquired_data = None
            self.buffered_chans = None
            self.extract_measurements(raw_data, waits_in_use)
            self.h5_file = None
            self.buffered_rate = None
            msg = 'data written, time taken: %ss' % str(time.time() - start_time)
        else:
            msg = 'No acquisitions in this shot.'
        self.logger.info(msg)

        return True

    def extract_measurements(self, raw_data, waits_in_use):
        self.logger.debug('extract_measurements')
        if waits_in_use:
            # There were waits in this shot. We need to wait until the other process has
            # determined their durations before we proceed:
            self.wait_durations_analysed.wait(self.h5_file)

        with h5py.File(self.h5_file, 'a') as hdf5_file:
            if waits_in_use:
                # get the wait start times and durations
                waits = hdf5_file['/data/waits']
                wait_times = waits['time']
                wait_durations = waits['duration']
            try:
                acquisitions = hdf5_file['/devices/' + self.device_name + '/AI']
            except KeyError:
                # No acquisitions!
                return
            try:
                measurements = hdf5_file['/data/traces']
            except KeyError:
                # Group doesn't exist yet, create it:
                measurements = hdf5_file.create_group('/data/traces')

            t0 = self.AI_start_delay
            for connection, label, t_start, t_end, _, _, _ in acquisitions:
                connection = _ensure_str(connection)
                label = _ensure_str(label)
                if waits_in_use:
                    # add durations from all waits that start prior to t_start of
                    # acquisition
                    t_start += wait_durations[(wait_times < t_start)].sum()
                    # compare wait times to t_end to allow for waits during an
                    # acquisition
                    t_end += wait_durations[(wait_times < t_end)].sum()
                i_start = int(np.ceil(self.buffered_rate * (t_start - t0)))
                i_end = int(np.floor(self.buffered_rate * (t_end - t0)))
                # np.ceil does what we want above, but float errors can miss the
                # equality:
                if t0 + (i_start - 1) / self.buffered_rate - t_start > -2e-16:
                    i_start -= 1
                # We want np.floor(x) to yield the largest integer < x (not <=):
                if t_end - t0 - i_end / self.buffered_rate < 2e-16:
                    i_end -= 1
                # IBS: we sometimes find that t_end (with waits) gives a time
                # after the end of acquisition.  The following line
                # will produce return a shorter than expected array if i_end
                # is larger than the length of the array.
                values = raw_data[connection][i_start : i_end + 1]
                i_end = i_start + len(values) - 1 # re-measure i_end

                t_i = t0 + i_start / self.buffered_rate
                t_f = t0 + i_end / self.buffered_rate
                times = np.linspace(t_i, t_f, len(values), endpoint=True)
                dtypes = [('t', np.float64), ('values', np.float32)]
                data = np.empty(len(values), dtype=dtypes)
                data['t'] = times
                data['values'] = values
                measurements.create_dataset(label, data=data)

    def abort_buffered(self):
        return self.transition_to_manual(True)

    def abort_transition_to_buffered(self):
        return self.transition_to_manual(True)

    def program_manual(self, values):
        return {}


class NI_DAQmxCounterWorker(Worker):
    """Counter acquisition using CI table."""

    def init(self):
        # Prevent interference between the read callback and the shutdown code:
        self.tasklock = threading.RLock()

        # Assigned on a per-shot basis and cleared afterward:
        self.buffered_mode = False
        self.h5_file = None
        self.instructions = []
        self.buffered_chans = []
        self.data_buffer = []
        self.daq_status = []
        self.data_saver = []
        self.online_monitor = None

        self.tasks = []
        self.thread_polling_data = []
        self.event_task_stopped = None
        self.manual_counters = {}
        self.manual_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def shutdown(self):
        for counter_name in list(self.manual_counters):
            self.stop_manual_counter(counter_name)
        self.manual_udp_socket.close()
        if len(self.tasks) > 0:
            self._stop_task()

    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):
        self.logger.debug('transition_to_buffered')
        for counter_name in list(self.manual_counters):
            self.stop_manual_counter(counter_name)

        self.h5_file = h5file
        with h5py.File(h5file, 'r') as f:
            group = f['/devices/' + device_name]
            if 'CI' not in group:
                return initial_values
            ci_table = group['CI'][:]

        self.instructions = []
        self.buffered_chans = []
        self.data_buffer = []
        self.daq_status = []
        self.data_saver = []
        self.online_monitor = OnlineMonitor()

        for i_task, row in enumerate(ci_table):
            self.instructions.append(
                {
                    'connection': _ensure_str(row['connection']),
                    'edge': _ensure_str(row['edge terminal']),
                    'gate': _ensure_str(row['gate terminal']),
                    'sample': _ensure_str(row['sample terminal']),
                    'max_sampling_rate': row['max_sampling_rate'],
                    'buffer_size': row['buffer_size'],
                    'polling_interval': row['polling_interval'],
                    'label': _ensure_str(row['label']),
                }
            )
            instruction = self.instructions[-1]

            self.buffered_chans.append(instruction["connection"])
            self.data_buffer.append(np.zeros((instruction["buffer_size"],), dtype=np.uint32))
            self.daq_status.append({})
            self.data_saver.append(
                DataSaver(
                    self.h5_file,
                    device_name=self.device_name,
                    acquisition_type="count",
                    data_label=instruction["label"]
                )
            )
            self.data_saver[-1].open_for_writing()
        
        self.buffered_mode = True
        self._start_task(self.instructions)

        print("[NI_DAQmxCounterWorker] finished transition_to_buffered")

        return {}

    def transition_to_manual(self, abort=False):
        self.logger.debug('[CounterWorker] transition_to_manual')

        if not self.buffered_mode:
            return True
        if len(self.buffered_chans) > 0:
            self._stop_task()

        self.logger.debug('[CounterWorker] task stopped')

        if abort:
            for status in self.daq_status:
                status["aborted"] = True

        for data_saver, daq_status in zip(self.data_saver, self.daq_status):
            data_saver.add_attribute("daq_status", json.dumps(daq_status))
            self.logger.debug(f"[CounterWorker] Close data file of {data_saver.data_label}")
            data_saver.close_data_file()
            self.logger.debug(f"[CounterWorker] Merge data in {data_saver.data_label} to the shot file")
            data_saver.merge_into_shot()

        self.buffered_mode = False
        self.h5_file = None
        self.instructions = []
        self.buffered_chans = []
        self.data_buffer = []
        self.daq_status = []
        self.data_saver = []
        self.online_monitor.close()
        self.online_monitor = None

        self.logger.info('transitioning to manual mode, task stopped')

        return True

    def abort_buffered(self):
        return self.transition_to_manual(True)

    def abort_transition_to_buffered(self):
        return self.transition_to_manual(True)

    def program_manual(self, values):
        return {}

    def _declared_counter_connections(self):
        return {
            counter['connection']
            for counter in getattr(self, 'declared_counters', [])
        }

    def _declared_counter_numbers(self):
        return {
            split_conn_CI(connection.lower())
            for connection in self._declared_counter_connections()
        }

    def _counter_internal_output_terminal(self, counter_connection):
        if '/' in counter_connection:
            return '/' + counter_connection.lstrip('/') + 'InternalOutput'
        return '/%s/%sInternalOutput' % (self.MAX_name, counter_connection)

    def _create_counter_output_task(self, counter_connection, rate):
        task = PyDAQmx.Task()
        chan = counter_connection
        if '/' not in chan:
            chan = '%s/%s' % (self.MAX_name, chan)
        task.CreateCOPulseChanFreq(
            chan,
            "",
            PyDAQmx.DAQmxConstants.DAQmx_Val_Hz,
            PyDAQmx.DAQmxConstants.DAQmx_Val_Low,
            0.0,
            rate,
            0.5,
        )
        task.SetCOPulseTerm("", "")
        task.CfgImplicitTiming(
            PyDAQmx.DAQmxConstants.DAQmx_Val_ContSamps, 1000
        )
        task.TaskControl(PyDAQmx.DAQmxConstants.DAQmx_Val_Task_Commit)
        return task

    def _manual_counter_values(
        self,
        counts,
        previous_count,
        scale,
    ):
        if len(counts) == 0:
            return np.array([], dtype=np.float64), previous_count
        if previous_count is None:
            if len(counts) < 2:
                return np.array([], dtype=np.float64), int(counts[-1])
            diffs = np.diff(counts.astype(np.int64))
        else:
            values = np.concatenate(([previous_count], counts.astype(np.int64)))
            diffs = np.diff(values)
        return diffs.astype(np.float64) * scale, int(counts[-1])

    def start_manual_counter(self, counter_name, counter, config):
        with self.tasklock:
            if counter_name in self.manual_counters:
                raise RuntimeError("Manual counter '%s' is already running" % counter_name)

            connection = counter['connection']
            for state in self.manual_counters.values():
                if state['counter']['connection'] == connection:
                    raise RuntimeError(
                        "Counter input '%s' is already in use" % connection
                    )

            sample_clock = config['sample_clock']
            rate = float(config['rate'])
            buffer_size = int(config['buffer_size'])
            fetch_interval = max(0.02, float(config['fetch_interval']))
            multiplication_factor = float(config['multiplication_factor'])
            average_count = int(config['average_count'])
            udp_host = config.get('udp_host', '')
            udp_port = int(config.get('udp_port', 0))

            if sample_clock == 'connection_table':
                sample = counter['sample']
                if not sample:
                    raise RuntimeError(
                        "Counter '%s' has no sample_terminal in the connection table"
                        % counter_name
                    )
                scale = multiplication_factor
                sample_clock_rate = None
                co_task = None
            else:
                sample_clock_num = split_conn_CI(sample_clock.lower())
                if sample_clock_num in self._declared_counter_numbers():
                    raise RuntimeError(
                        "Sample clock counter '%s' is declared as a counter input"
                        % sample_clock
                    )
                for state in self.manual_counters.values():
                    if state['sample_clock'] == sample_clock:
                        raise RuntimeError(
                            "Sample clock counter '%s' is already in use" % sample_clock
                        )
                co_task = self._create_counter_output_task(sample_clock, rate)
                sample = self._counter_internal_output_terminal(sample_clock)
                sample_clock_rate = rate
                scale = rate * multiplication_factor

            inst = {
                'connection': connection,
                'edge': counter['edge'],
                'gate': counter['gate'],
                'sample': sample,
                'max_sampling_rate': rate,
                'buffer_size': buffer_size,
            }
            ci_task = PyDAQmx.Task()
            self._set_count_task(ci_task, inst)

            state = {
                'counter': counter,
                'ci_task': ci_task,
                'co_task': co_task,
                'sample_clock': sample_clock,
                'sample_clock_rate': sample_clock_rate,
                'scale': scale,
                'buffer': np.zeros((buffer_size,), dtype=np.uint32),
                'daq_status': {},
                'last_count': None,
                'values': deque(maxlen=average_count),
                'udp_host': udp_host,
                'udp_port': udp_port,
                'fetch_interval': fetch_interval,
            }
            self.manual_counters[counter_name] = state

            try:
                ci_task.StartTask()
                if co_task is not None:
                    co_task.StartTask()
            except Exception:
                self.stop_manual_counter(counter_name)
                raise

            return {'status': 'running'}

    def stop_manual_counter(self, counter_name):
        with self.tasklock:
            state = self.manual_counters.pop(counter_name, None)
            if state is None:
                return {'status': 'stopped'}
            for task_name in ('co_task', 'ci_task'):
                task = state[task_name]
                if task is None:
                    continue
                try:
                    task.StopTask()
                except Exception:
                    self.logger.debug(
                        "Ignoring error stopping %s for manual counter %s",
                        task_name,
                        counter_name,
                        exc_info=True,
                    )
                task.ClearTask()
            return {'status': 'stopped'}

    def fetch_manual_counter(self, counter_name):
        state = self.manual_counters.get(counter_name)
        if state is None:
            return {'status': 'stopped', 'samples_read': 0}

        samples_read = self._read_data(
            state['ci_task'],
            PyDAQmx.DAQmxConstants.DAQmx_Val_Auto,
            0,
            state['buffer'],
            state['daq_status'],
        )
        if samples_read <= 0:
            return {'status': 'running', 'samples_read': 0}

        counts = np.array(state['buffer'][:samples_read], copy=True)
        values, state['last_count'] = self._manual_counter_values(
            counts, state['last_count'], state['scale']
        )
        for value in values:
            state['values'].append(float(value))
            if state['udp_host'] and state['udp_port']:
                payload = ("%.12g" % float(value)).encode("utf-8")
                try:
                    self.manual_udp_socket.sendto(
                        payload, (state['udp_host'], state['udp_port'])
                    )
                except OSError as exc:
                    state['daq_status']['udp_error'] = str(exc)
                    self.logger.warning(
                        "Manual counter UDP send failed for %s: %s",
                        counter_name,
                        exc,
                    )

        if len(values) == 0:
            return {'status': 'running', 'samples_read': samples_read}

        latest = float(values[-1])
        moving_average = float(np.mean(state['values'])) if state['values'] else latest
        status = 'running'
        if state['daq_status'].get('has_overflow'):
            status = 'running (overflow)'
        if state['daq_status'].get('udp_error'):
            status = 'running (UDP error: %s)' % state['daq_status']['udp_error']
        return {
            'status': status,
            'samples_read': samples_read,
            'latest_value': latest,
            'moving_average': moving_average,
            'values': [float(value) for value in values],
        }

    def _read_data(self, task, read_samples: int, timeout: float, buffer: np.array, daq_status=None):
        try:
            buffer_size = buffer.shape[0]
            samples_per_channel_read = PyDAQmx.DAQmxTypes.int32()

            task.ReadCounterU32(read_samples, timeout, buffer, buffer_size, PyDAQmx.byref(samples_per_channel_read), None)

            if samples_per_channel_read.value == buffer_size:
                sys.stderr.write("Data overflow happened in counter. Increase the buffer size.\n")
                if not daq_status is None:
                    daq_status["has_overflow"] = True

            return int(samples_per_channel_read.value)
        except SamplesNotYetAvailableError:
            return 0 
        except DAQmxError as e:
            msg = str(e)
            if "-200284" in msg: # Timeout error
                return 0
            raise

    def _poll_data(self, i_task: int, interval: float):
        while not self.event_task_stopped.is_set():
            samples_read = self._read_data(
                self.tasks[i_task],
                PyDAQmx.DAQmxConstants.DAQmx_Val_Auto,
                0,
                self.data_buffer[i_task],
                self.daq_status[i_task],
            )

            if samples_read > 0:
                data = np.array(self.data_buffer[i_task][:samples_read], copy=True)
                saver = self.data_saver[i_task]
                ds_name = "data"

                data_save_succeeded = False
                max_trial = 8
                wait_interval_between_trial = 0.05
                trial = 0
                while not data_save_succeeded and trial < max_trial:
                    f = saver.get_open_file()
                    if f is None:
                        time.sleep(wait_interval_between_trial)
                        trial += 1
                        continue
                    if ds_name not in f:
                        f.create_dataset(
                            ds_name,
                            data=data,
                            maxshape=(None,),
                            chunks=True,
                            dtype=data.dtype,
                        )
                    else:
                        ds = f[ds_name]
                        old_len = ds.shape[0]
                        ds.resize((old_len + samples_read,))
                        ds[old_len:] = data
                    data_save_succeeded = True
                if not data_save_succeeded:
                    raise RuntimeError("[NI_DAQmxCounter] failed to save data after {max_trial} attempts. Data was lost.")

            if samples_read > 0 and self.online_monitor:
                dummy_interval = interval * 1e9 / samples_read # in nanoseconds

                now_ns = time.time_ns()

                for i_sample in range(samples_read):
                    try:
                        self.online_monitor.send_point(
                            measurement="count",
                            tags={
                                "shot_file": Path(self.h5_file).stem,
                                "device_name": self.device_name,
                            },
                            fields={
                                self.instructions[i_task]["label"]: self.data_buffer[i_task][i_sample],
                            },
                            timestamp_ns=now_ns - dummy_interval * (samples_read - i_sample - 1)
                        )
                    except Exception as exc:
                        self.logger.warning("Online monitor send failed: %s", exc)
                        break

            time.sleep(interval)

    def _set_count_task(self, task, inst):
        """Set count task.

        Buffer size specification must be matched in that in transition_to_buffered method.
        """
        def fix_term_name(name: str):
            if '/' not in name:
                name = f"{self.MAX_name}/{name}"
            return name

        chan = fix_term_name(inst['connection'])
        edge = inst['edge']
        gate = inst['gate']
        sample = inst['sample']
        max_sampling_rate = inst["max_sampling_rate"]
        buffer_size = inst["buffer_size"]

        try:
            task.CreateCICountEdgesChan(
                chan, "", PyDAQmx.DAQmxConstants.DAQmx_Val_Rising, 0, PyDAQmx.DAQmxConstants.DAQmx_Val_CountUp
            )
            if edge:
                task.SetCICountEdgesTerm(chan, edge)
            if gate:
                task.SetPauseTrigType(PyDAQmx.DAQmxConstants.DAQmx_Val_DigLvl)
                task.SetDigLvlPauseTrigWhen(PyDAQmx.DAQmxConstants.DAQmx_Val_Low);
                task.SetDigLvlPauseTrigSrc(gate);
            if sample:
                task.CfgSampClkTiming(sample, max_sampling_rate, PyDAQmx.DAQmxConstants.DAQmx_Val_Rising, PyDAQmx.DAQmxConstants.DAQmx_Val_ContSamps, buffer_size)
        finally:
            pass

    def _start_task(self, insts: list[dict]):
        if len(self.tasks) > 0:
            raise RuntimeError('Task already running')

        self.tasks = []
        self.thread_polling_data = []
        self.event_task_stopped = None

        for i_task, inst in enumerate(insts):
            self.tasks.append(PyDAQmx.Task())
            self._set_count_task(self.tasks[-1], inst)
            self.thread_polling_data.append(
                threading.Thread(
                    target=self._poll_data,
                    args=(i_task, inst["polling_interval"]),
                    daemon=True
                )
            )

        self.event_task_stopped = threading.Event()

        for i_task, task in enumerate(self.tasks):
            task.StartTask()
            self.thread_polling_data[i_task].start()

    def _stop_task(self):
        with self.tasklock:
            self.logger.debug('[CounterWorker] Stopping tasks')

            if len(self.tasks) == 0:
                raise RuntimeError('Task not running')

            self.event_task_stopped.set()
            self.logger.debug('[CounterWorker] Event of task stopped is set')

            for i_task, task in enumerate(self.tasks):
                task.StopTask()
                self.logger.debug(f'[CounterWorker] Task {i_task} stopped')

                self.thread_polling_data[i_task].join()
                self.logger.debug(f'[CounterWorker] Thread polling data {i_task} joined')

                data_buffer = self.data_buffer[i_task]
                query_sample_size = data_buffer.shape[0]

                while query_sample_size > 0:
                    read_sample_size = self._read_data(task, query_sample_size, 0, data_buffer)
                    
                    if read_sample_size == 0:
                        query_sample_size -= 1
                    else:
                        break

                self.logger.debug(f'[CounterWorker] Finished reading data from task {i_task}')

                task.ClearTask()

            self.tasks = []
            self.thread_polling_data = []
            self.event_task_stopped = None


class NI_DAQmxWaitMonitorWorker(Worker):
    def init(self):

        self.all_waits_finished = Event('all_waits_finished', type='post')
        self.wait_durations_analysed = Event('wait_durations_analysed', type='post')
        self.wait_completed = Event('wait_completed', type='post')

        # Set on a per-shot basis and cleared afterward:
        self.h5_file = None
        self.CI_task = None
        self.DO_task = None
        self.wait_table = None
        self.semiperiods = None
        self.wait_monitor_thread = None

        # Saved error in case one occurs in the thread, we can raise it later in
        # transition_to_manual:
        self.wait_monitor_thread_exception = None
        # To trigger early shutdown of the wait monitor thread:
        self.shutting_down = False

        # Does this device have the "incomplete sample detection" feature? This
        # determines whether the first sample on our semiperiod counter input task will
        # be automatically discarded before we see it, or whether we will have to
        # discard it ourselves
        self.incomplete_sample_detection = incomplete_sample_detection(self.MAX_name)

        # Data for timeout triggers:
        if self.timeout_trigger_type == 'rising':
            trigger_value = 1
            rearm_value = 0
        elif self.timeout_trigger_type == 'falling':
            trigger_value = 0
            rearm_value = 1
        else:
            msg = 'timeout_trigger_type  must be "rising" or "falling", not "{}".'
            raise ValueError(msg.format(self.timeout_trigger_type))
        self.timeout_trigger = np.array([trigger_value], dtype=np.uint8)
        self.timeout_rearm = np.array([rearm_value], dtype=np.uint8)

    def shutdown(self):
        self.stop_tasks(True)

    def read_edges(self, npts, timeout=None):
        """Wait up to the given timeout in seconds for an edge on the wait monitor and
        and return the duration since the previous edge. Return None upon timeout."""
        samples_read = int32()
        # If no timeout, call read repeatedly with a 0.2 second timeout to ensure we
        # don't block indefinitely and can still abort.
        if timeout is None:
            read_timeout = 0.2
        else:
            read_timeout = timeout
        read_array = np.zeros(npts)
        while True:
            if self.shutting_down:
                raise RuntimeError('Stopped before expected number of samples acquired')
            try:
                self.CI_task.ReadCounterF64(
                    npts, read_timeout, read_array, npts, samples_read, None
                )
            except SamplesNotYetAvailableError:
                if timeout is None:
                    continue
                return None
            return read_array

    def wait_monitor(self):
        try:
            # Read edge times from the counter input task, indiciating the times of the
            # pulses that occur at the start of the experiment and after every wait. If a
            # timeout occurs, pulse the timeout output to force a resume of the master
            # pseudoclock. Save the resulting
            self.logger.debug('Wait monitor thread starting')
            with self.kill_lock:
                self.logger.debug('Waiting for start of experiment')
                # Wait for the pulse indicating the start of the experiment:
                if self.incomplete_sample_detection:
                    semiperiods = self.read_edges(1, timeout=None)
                else:
                    semiperiods = self.read_edges(2, timeout=None)
                self.logger.debug('Experiment started, got edges:' + str(semiperiods))
                # May have been one or two edges, depending on whether the device has
                # incomplete sample detection. We are only interested in the second one
                # anyway, it tells us how long the initial pulse was. Store the pulse width
                # for later, we will use it for making timeout pulses if necessary. Note
                # that the variable current_time is labscript time, so it will be reset
                # after each wait to the time of that wait plus pulse_width.
                current_time = pulse_width = semiperiods[-1]
                self.semiperiods.append(semiperiods[-1])
                # Alright, we're now a short way into the experiment.
                for wait in self.wait_table:
                    # How long until when the next wait should timeout?
                    timeout = wait['time'] + wait['timeout'] - current_time
                    timeout = max(timeout, 0)  # ensure non-negative
                    # Wait that long for the next pulse:
                    self.logger.debug('Waiting for pulse indicating end of wait')
                    semiperiods = self.read_edges(2, timeout)
                    # Did the wait finish of its own accord, or time out?
                    if semiperiods is None:
                        # It timed out. If there is a timeout device, send a trigger to
                        # resume the clock!
                        if self.DO_task is not None:
                            msg = """Wait timed out; retriggering clock with {:.3e} s
                                pulse ({} edge)"""
                            msg = msg.format(pulse_width, self.timeout_trigger_type)
                            self.logger.debug(dedent(msg))
                            self.send_resume_trigger(pulse_width)
                        else:
                            msg = """Specified wait timeout exceeded, but there is no
                                timeout device with which to resume the experiment.
                                Continuing to wait."""
                            self.logger.warning(dedent(msg))
                        # Keep waiting for the clock to resume:
                        self.logger.debug('Waiting for pulse indicating end of wait')
                        semiperiods = self.read_edges(2, timeout=None)
                    # Alright, now we're at the end of the wait.
                    self.semiperiods.extend(semiperiods)
                    self.logger.debug('Wait completed')
                    current_time = wait['time'] + semiperiods[-1]
                    # Inform any interested parties that a wait has completed:
                    postdata = _ensure_str(wait['label'])
                    self.wait_completed.post(self.h5_file, data=postdata)
                # Inform any interested parties that waits have all finished:
                self.logger.debug('All waits finished')
                self.all_waits_finished.post(self.h5_file)
        except Exception:
            self.logger.exception('Exception in wait monitor thread:')
            # Save the exception so it can be raised in transition_to_manual
            self.wait_monitor_thread_exception = sys.exc_info()

    def send_resume_trigger(self, pulse_width):
        written = int32()
        # Trigger:
        self.DO_task.WriteDigitalLines(
            1, True, 1, DAQmx_Val_GroupByChannel, self.timeout_trigger, written, None
        )
        # Wait however long we observed the first pulse of the experiment to be. In
        # practice this is likely to be negligible compared to the other software delays
        # here, but in case it is larger we'd better wait:
        time.sleep(pulse_width)
        # Rearm trigger:
        self.DO_task.WriteDigitalLines(
            1, True, 1, DAQmx_Val_GroupByChannel, self.timeout_rearm, written, None
        )

    def stop_tasks(self, abort):
        self.logger.debug('stop_tasks')
        if self.wait_monitor_thread is not None:
            if abort:
                # This will cause the wait_monitor thread to raise an exception within a
                # short time, allowing us to join it before it would otherwise be done.
                self.shutting_down = True
            self.wait_monitor_thread.join()
            self.wait_monitor_thread = None
            self.shutting_down = False
            if not abort and self.wait_monitor_thread_exception is not None:
                # Raise any unexpected errors from the wait monitor thread:
                _reraise(*self.wait_monitor_thread_exception)
            self.wait_monitor_thread_exception = None
            if not abort:
                # Don't want errors about incomplete task to be raised if we are aborting:
                self.CI_task.StopTask()
            if self.DO_task is not None:
                self.DO_task.StopTask()
        if self.CI_task is not None:
            self.CI_task.ClearTask()
            self.CI_task = None
        if self.DO_task is not None:
            self.DO_task.ClearTask()
            self.DO_task = None
        self.logger.debug('finished stop_tasks')

    def start_tasks(self):

        # The counter acquisition task:
        self.CI_task = Task()
        CI_chan = self.MAX_name + '/' + self.wait_acq_connection
        # What is the longest time in between waits, plus the timeout of the
        # second wait?
        interwait_times = np.diff([0] + list(self.wait_table['time']))
        max_measure_time = max(interwait_times + self.wait_table['timeout'])
        # Allow for software delays in timeouts.
        max_measure_time += 1.0
        min_measure_time = self.min_semiperiod_measurement
        self.logger.debug(
            "CI measurement range is: min: %f max: %f",
            min_measure_time,
            max_measure_time,
        )
        self.CI_task.CreateCISemiPeriodChan(
            CI_chan, '', min_measure_time, max_measure_time, DAQmx_Val_Seconds, ""
        )
        num_edges = 2 * (len(self.wait_table) + 1)
        self.CI_task.CfgImplicitTiming(DAQmx_Val_ContSamps, num_edges)
        self.CI_task.StartTask()

        # The timeout task:
        if self.wait_timeout_MAX_name is not None:
            self.DO_task = Task()
            DO_chan = self.wait_timeout_MAX_name + '/' + self.wait_timeout_connection
            self.DO_task.CreateDOChan(DO_chan, "", DAQmx_Val_ChanForAllLines)
            # Ensure timeout trigger is armed:
            written = int32()
            # Writing autostarts the task:
            self.DO_task.WriteDigitalLines(
                1, True, 1, DAQmx_Val_GroupByChannel, self.timeout_rearm, written, None
            )

    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):
        self.logger.debug('transition_to_buffered')
        self.h5_file = h5file
        with h5py.File(h5file, 'r') as hdf5_file:
            dataset = hdf5_file['waits']
            if len(dataset) == 0:
                # There are no waits. Do nothing.
                self.logger.debug('There are no waits, not transitioning to buffered')
                self.wait_table = None
                return {}
            self.wait_table = dataset[:]

        self.start_tasks()

        # An array to store the results of counter acquisition:
        self.semiperiods = []
        self.wait_monitor_thread = threading.Thread(target=self.wait_monitor)
        # Not a daemon thread, as it implements wait timeouts - we need it to stay alive
        # if other things die.
        self.wait_monitor_thread.start()
        self.logger.debug('finished transition to buffered')

        return {}

    def transition_to_manual(self, abort=False):
        self.logger.debug('transition_to_manual')
        self.stop_tasks(abort)
        if not abort and self.wait_table is not None:
            # Let's work out how long the waits were. The absolute times of each edge on
            # the wait monitor were:
            edge_times = np.cumsum(self.semiperiods)
            # Now there was also a rising edge at t=0 that we didn't measure:
            edge_times = np.insert(edge_times, 0, 0)
            # Ok, and the even-indexed ones of these were rising edges.
            rising_edge_times = edge_times[::2]
            # Now what were the times between rising edges?
            periods = np.diff(rising_edge_times)
            # How does this compare to how long we expected there to be between the
            # start of the experiment and the first wait, and then between each pair of
            # waits? The difference will give us the waits' durations.
            resume_times = self.wait_table['time']
            # Again, include the start of the experiment, t=0:
            resume_times = np.insert(resume_times, 0, 0)
            run_periods = np.diff(resume_times)
            wait_durations = periods - run_periods
            waits_timed_out = wait_durations > self.wait_table['timeout']

            # Work out how long the waits were, save them, post an event saying so:
            dtypes = [
                ('label', 'a256'),
                ('time', float),
                ('timeout', float),
                ('duration', float),
                ('timed_out', bool),
            ]
            data = np.empty(len(self.wait_table), dtype=dtypes)
            data['label'] = self.wait_table['label']
            data['time'] = self.wait_table['time']
            data['timeout'] = self.wait_table['timeout']
            data['duration'] = wait_durations
            data['timed_out'] = waits_timed_out
            with h5py.File(self.h5_file, 'a') as hdf5_file:
                hdf5_file.create_dataset('/data/waits', data=data)
            self.wait_durations_analysed.post(self.h5_file)

        self.h5_file = None
        self.semiperiods = None
        return True

    def abort_buffered(self):
        return self.transition_to_manual(True)

    def abort_transition_to_buffered(self):
        return self.transition_to_manual(True)

    def program_manual(self, values):
        return {}
