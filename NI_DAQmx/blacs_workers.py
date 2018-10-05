#####################################################################
#                                                                   #
# /NI_DAQmx/workers.py                                              #
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

import time
import logging
import traceback
import threading

from PyDAQmx import *
from PyDAQmx.DAQmxConstants import *
from PyDAQmx.DAQmxTypes import *

import numpy as np
import labscript_utils.h5_lock
import h5py
import zprocess

import labscript_utils.properties as properties
from labscript_utils import dedent
from labscript_utils.connections import _ensure_str
from labscript_utils.numpy_dtype_workaround import dtype_workaround

from blacs.tab_base_classes import Worker

from .utils import split_conn_port, split_conn_DO


class NI_DAQmxOutputWorker(Worker):
    def init(self):
        self.check_version()
        # Reset Device: clears previously added routes etc. Note: is insufficient for
        # some devices, which require power cycling to truly reset.
        DAQmxResetDevice(self.MAX_name)
        self.setup_manual_mode_tasks()

    def stop_and_clear_tasks(self):
        if self.AO_task is not None:
            self.AO_task.StopTask()
            self.AO_task.ClearTask()
            self.AO_task = None
        if self.DO_task is not None:
            self.DO_task.StopTask()
            self.DO_task.ClearTask()
            self.DO_task = None

    def shutdown(self):
        self.stop_and_clear_tasks()

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

    def setup_manual_mode_tasks(self):
        # Create tasks:
        if self.num_AO > 0:
            self.AO_task = Task()
            self.AO_data = np.zeros((self.num_AO,), dtype=np.float64)
        else:
            self.AO_task = None

        if self.ports:
            num_DO = sum(port['num_lines'] for port in self.ports.values())
            self.DO_task = Task()
            self.DO_data = np.zeros(num_DO, dtype=np.uint8)
        else:
            self.DO_task = None

        # Setup AO channels
        for i in range(self.num_AO):
            con = self.MAX_name + "/ao%d" % i
            self.AO_task.CreateAOVoltageChan(
                con, "", self.Vmin, self.Vmax, DAQmx_Val_Volts, None
            )

        # Setup DO channels
        for port_str in sorted(self.ports, key=split_conn_port):
            num_lines = self.ports[port_str]["num_lines"]
            # need to create chans in multiples of 8:
            ranges = []
            for i in range(num_lines // 8):
                ranges.append((8 * i, 8 * i + 7))
            div, remainder = divmod(num_lines, 8)
            if remainder:
                ranges.append((div * 8, div * 8 + remainder - 1))
            for start, stop in ranges:
                con = '%s/%s/line%d:%d' % (self.MAX_name, port_str, start, stop)
                self.DO_task.CreateDOChan(con, "", DAQmx_Val_ChanForAllLines)

        # Start tasks:
        if self.AO_task is not None:
            self.AO_task.StartTask()
        if self.DO_task is not None:
            self.DO_task.StartTask()

    def program_manual(self, front_panel_values):
        written = int32()
        for i in range(self.num_AO):
            self.AO_data[i] = front_panel_values['ao%d' % i]
        if self.AO_task is not None:
            self.AO_task.WriteAnalogF64(
                1, True, 1, DAQmx_Val_GroupByChannel, self.AO_data, byref(written), None
            )
        for i, conn in enumerate(self.DO_hardware_names):
            self.DO_data[i] = front_panel_values[conn]
        if self.DO_task is not None:
            self.DO_task.WriteDigitalLines(
                1, True, 1, DAQmx_Val_GroupByChannel, self.DO_data, byref(written), None
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

    def program_buffered_DO(self, DO_table):
        """Create the DO task and program in the DO table for a shot. Return a
        dictionary of the final values of each channel in use"""
        if DO_table is None:
            return {}
        self.DO_task = Task()
        written = int32()
        ports = DO_table.dtype.names

        final_values = {}
        for port_str in ports:
            # Add each port to the task:
            con = '%s/%s' % (self.MAX_name, port_str)
            self.DO_task.CreateDOChan(con, "", DAQmx_Val_ChanForAllLines)

            # Collect the final values of the lines on this port:
            port_final_value = DO_table[port_str][-1]
            for line in range(self.ports[port_str]["num_lines"]):
                # Extract each digital value from the packed bits:
                line_final_value = bool((1 << line) & port_final_value)
                final_values['%s/line%d' % (port_str, line)] = int(line_final_value)

        # Methods for writing data to the task depending on the datatype of each port:
        write_methods = {
            np.uint8: self.DO_task.WriteDigitalU8,
            np.uint16: self.DO_task.WriteDigitalU16,
            np.uint32: self.DO_task.WriteDigitalU32,
        }

        if self.static_DO:
            # Static DO. Start the task and write data, no timing configuration.
            self.DO_task.StartTask()
            # Write data for each port:
            for port_str in ports:
                data = DO_table[port_str]
                write_method = write_methods[data.dtype.type]
                write_method(
                    1,  # npts
                    False,  # autostart
                    10.0,  # timeout
                    DAQmx_Val_GroupByChannel,
                    data,
                    byref(written),
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

            # Write data for each port:
            for port_str in ports:
                # All but the last sample as mentioned above
                data = DO_table[port_str][:-1]
                write_method = write_methods[data.dtype.type]
                write_method(
                    npts,
                    False,  # autostart
                    10.0,  # timeout
                    DAQmx_Val_GroupByChannel,
                    data,
                    byref(written),
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

        # Obtain a view that is a regular array:
        AO_table = AO_table.view((AO_table.dtype[0], len(AO_table.dtype.names)))
        # And convert to 64 bit floats:
        AO_table = AO_table.astype(np.float64)

        if self.static_AO:
            # Static AO. Start the task and write data, no timing configuration.
            self.AO_task.StartTask()
            self.AO_task.WriteAnalogF64(
                1, True, 10.0, DAQmx_Val_GroupByChannel, AO_table, byref(written), None
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
                byref(written),
                None,
            )

            # Go!
            self.AO_task.StartTask()

        return final_values

    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):
        # Store the initial values in case we have to abort and restore them:
        self.initial_values = initial_values

        # Stop the manual mode output tasks, if any:
        self.stop_and_clear_tasks()

        # Get the data to be programmed into the output tasks:
        AO_table, DO_table = self.get_output_tables(h5file, device_name)

        # Mirror the clock terminal, if applicable:
        self.set_mirror_clock_terminal_connected(True)

        # Program the output tasks and retrieve the final values of each output:
        DO_final_values = self.program_buffered_DO(DO_table)
        AO_final_values = self.program_buffered_AO(AO_table)

        final_values = {}
        final_values.update(DO_final_values)
        final_values.update(AO_final_values)

        return final_values

    def transition_to_manual(self, abort=False):
        # Stop output tasks and call program_manual. Only call StopTask if not aborting.
        # Otherwise results in an error if output was incomplete. If aborting, call
        # ClearTask only.
        npts = uInt64()
        samples = uInt64()
        tasks = []
        if self.AO_task is not None:
            tasks.append([self.AO_task, self.static_AO, 'AO'])
            self.AO_task = None
        if self.DO_task is not None:
            tasks.append([self.DO_task, self.static_DO, 'DO'])
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

        # Set up manual mode tasks again:
        self.setup_manual_mode_tasks()
        if abort:
            # Reprogram the initial states:
            self.program_manual(self.initial_values)

        return True

    def abort_transition_to_buffered(self):
        return self.transition_to_manual(True)

    def abort_buffered(self):
        return self.transition_to_manual(True)


class NI_DAQmxAcquisitionWorker(Worker):
    def init(self):
        self.task_running = False
        self.daqlock = threading.Condition()
        # Channel details
        self.channels = []
        self.rate = 1000.0
        self.samples_per_channel = 1000
        self.ai_start_delay = 25e-9
        self.h5_file = ""
        self.buffered_channels = []
        self.buffered_rate = 0
        self.buffered = False
        self.buffered_data = None
        self.buffered_data_list = []

        self.task = None
        self.abort = False

        # An event for knowing when the wait durations are known, so that we may use
        # them to chunk up acquisition data:
        self.wait_durations_analysed = zprocess.Event('wait_durations_analysed')

        self.daqmx_read_thread = threading.Thread(target=self.daqmx_read)
        self.daqmx_read_thread.daemon = True
        self.daqmx_read_thread.start()

    def shutdown(self):
        if self.task_running:
            self.stop_task()

    def daqmx_read(self):
        logger_fmt = 'BLACS.%s_%s.acquisition.daqmxread'
        logger = logging.getLogger(logger_fmt % (self.device_name, self.worker_name))
        logger.info('Starting')

        try:
            while True:
                with self.daqlock:
                    logger.debug('Got daqlock')
                    while not self.task_running:
                        msg = """Task isn\'t running. Releasing daqlock and waiting to
                            reacquire it."""
                        logger.debug(dedent(msg))
                        self.daqlock.wait()
                    # logger.debug('Reading data from analogue inputs')
                    if self.buffered:
                        chnl_list = self.buffered_channels
                    else:
                        chnl_list = self.channels
                    try:
                        error = "Task did not return an error, but it should have"
                        acquisition_timeout = 5
                        error = self.task.ReadAnalogF64(
                            self.samples_per_channel,
                            acquisition_timeout,
                            DAQmx_Val_GroupByChannel,
                            self.ai_data,
                            self.samples_per_channel * len(chnl_list),
                            byref(self.ai_read),
                            None,
                        )
                        # logger.debug('Reading complete')
                        if error is not None and error != 0:
                            if error < 0:
                                raise Exception(error)
                            if error > 0:
                                logger.warning(error)
                    except Exception as e:
                        logger.exception('acquisition error')
                        if self.abort:
                            # If an abort is in progress, then we expect an exception
                            # here. Don't raise it.
                            logger.debug('ignoring error during abort.')
                            # Ensure the next iteration of this while loop doesn't
                            # happen until the task is restarted. The thread calling
                            # self.stop_task() is also setting self.task_running = False
                            # right about now, but we don't want to rely on it doing so
                            # in time. Doing it here too avoids a race condition.
                            self.task_running = False
                            continue
                        else:
                            # Error was likely a timeout error...some other device might
                            # be bing slow transitioning to buffered, so we haven't got
                            # our start trigger yet. Keep trying until task_running is
                            # False:
                            continue
                # send the data to the queue
                if self.buffered:
                    # rearrange ai_data into correct form
                    data = np.copy(self.ai_data)
                    self.buffered_data_list.append(data)
        except Exception:
            message = traceback.format_exc()
            logger.error('An exception happened:\n %s' % message)
            # self.to_parent.put(['error', message])
            # TODO: Tell the GUI process that this has a problem some how (status
            # check?)

    def setup_task(self):
        self.logger.debug('setup_task')
        # DAQmx Configure Code
        with self.daqlock:
            self.logger.debug('setup_task got daqlock')
            if self.task:
                self.task.ClearTask()
            if self.buffered:
                chnl_list = self.buffered_channels
                rate = self.buffered_rate
            else:
                chnl_list = self.channels
                rate = self.rate

            if len(chnl_list) < 1:
                return

            if rate < 1000:
                self.samples_per_channel = int(rate)
            else:
                self.samples_per_channel = 1000

            if rate < 1e2:
                self.buffer_per_channel = 1000
            elif rate < 1e4:
                self.buffer_per_channel = 10000
            elif rate < 1e6:
                self.buffer_per_channel = 100000
            else:
                self.buffer_per_channel = 1000000

            try:
                self.task = Task()
            except Exception as e:
                self.logger.error(str(e))
            self.ai_read = int32()
            total_samps = self.samples_per_channel * len(chnl_list)
            self.ai_data = np.zeros((total_samps,), dtype=np.float64)

            for chnl in chnl_list:
                self.task.CreateAIVoltageChan(
                    chnl, "", DAQmx_Val_RSE, -10.0, 10.0, DAQmx_Val_Volts, None
                )

            self.task.CfgSampClkTiming(
                "",
                rate,
                DAQmx_Val_Rising,
                DAQmx_Val_ContSamps,
                self.samples_per_channel,
            )

            # Variable buffer size helps avoid buffer underflows:
            self.task.CfgInputBuffer(self.buffer_per_channel)

            if self.buffered:
                # set up start on digital trigger
                self.task.CfgDigEdgeStartTrig(self.clock_terminal, DAQmx_Val_Rising)

            # DAQmx Start Code
            self.task.StartTask()
            # TODO: Need to do something about the time for buffered acquisition. Should
            # be related to when it starts (approx) How do we detect that?
            self.t0 = time.time() - time.timezone
            self.task_running = True
            self.daqlock.notify()
        self.logger.debug('finished setup_task')

    def stop_task(self):
        self.logger.debug('stop_task')
        with self.daqlock:
            self.logger.debug('stop_task got daqlock')
            if self.task_running:
                self.task_running = False
                self.task.StopTask()
                self.task.ClearTask()
            self.daqlock.notify()
        self.logger.debug('finished stop_task')

    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):
        # TODO: Do this line better!
        self.device_name = device_name

        self.logger.debug('transition_to_buffered')
        # stop current task
        self.stop_task()

        self.buffered_data_list = []

        # Save h5file path (for storing data later!)
        self.h5_file = h5file
        # read channels, acquisition rate, etc from H5 file
        h5_chnls = []
        with h5py.File(h5file, 'r') as f:
            group = f['/devices/' + device_name]
            if 'AI' not in group:
                # No acquisition
                return {}
            AI_table = group['AI'][:]
            device_props = properties.get(f, device_name, 'device_properties')
            ctable_props = properties.get(f, device_name, 'connection_table_properties')

        self.clock_terminal = ctable_props['clock_terminal']
        self.buffered_rate = device_props['acquisition_rate']

        chans = [device_name + '/' + _ensure_str(c) for c in AI_table['connection']]

        # Remove duplicates and sort:
        self.buffered_channels = sorted(set(chans))

        self.buffered = True
        if len(self.buffered_channels) == 1:
            self.buffered_data = np.zeros((1,), dtype=np.float64)
        else:
            self.buffered_data = np.zeros(
                (1, len(self.buffered_channels)), dtype=np.float64
            )
        self.setup_task()
        return {}

    def transition_to_manual(self, abort=False):
        self.logger.debug('transition_to_static')
        # Stop acquisition (this should really be done on a digital edge, but that is
        # for later! Maybe use a Counter) Set the abort flag so that the acquisition
        # thread knows to expect an exception in the case of an abort:
        #
        # TODO: This is probably bad because it shortly get's overwritten to False
        # However whether it has an effect depends on whether daqmx_read thread holds
        # the daqlock when self.stop_task() is called
        self.abort = abort
        self.stop_task()
        # Reset the abort flag so that unexpected exceptions are still raised:
        self.abort = False
        self.logger.info('transitioning to static, task stopped')
        # save the data acquired to the h5 file
        if not abort:
            with h5py.File(self.h5_file, 'a') as hdf5_file:
                data_group = hdf5_file['data']
                data_group.create_group(self.device_name)

            dtypes = [(c.split('/')[-1], np.float32) for c in self.buffered_channels]

            start_time = time.time()
            if self.buffered_data_list:
                npts = self.samples_per_channel * len(self.buffered_data_list)
                self.buffered_data = np.zeros(npts, dtype=dtype_workaround(dtypes))
                for i, data in enumerate(self.buffered_data_list):
                    data.shape = (len(self.buffered_channels), self.ai_read.value)
                    for j, (chan, dtype) in enumerate(dtypes):
                        start = i * self.samples_per_channel
                        end = start + self.samples_per_channel
                        self.buffered_data[chan][start:end] = data[j, :]
                    if i % 100 == 0:
                        msg = str(i / 100) + " time: " + str(time.time() - start_time)
                        self.logger.debug(msg)
                self.extract_measurements(self.device_name)
                msg = 'data written, time taken: %ss' % str(time.time() - start_time)
                self.logger.info(msg)

            self.buffered_data = None
            self.buffered_data_list = []

            # Send data to callback functions as requested (in one big chunk!)
            # self.result_queue.put([self.t0,self.rate,self.ai_read,len(self.channels),self.ai_data])

        # return to previous acquisition mode
        self.buffered = False
        self.setup_task()

        return True

    def extract_measurements(self, device_name):
        self.logger.debug('extract_measurements')
        with h5py.File(self.h5_file, 'a') as hdf5_file:
            waits_in_use = len(hdf5_file['waits']) > 0
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
                acquisitions = hdf5_file['/devices/' + device_name + '/AI']
            except KeyError:
                # No acquisitions!
                return
            try:
                measurements = hdf5_file['/data/traces']
            except KeyError:
                # Group doesn't exist yet, create it:
                measurements = hdf5_file.create_group('/data/traces')

            rate = self.buffered_rate
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
                i_start = int(np.ceil(rate * (t_start - self.ai_start_delay)))
                i_end = int(np.floor(rate * (t_end - self.ai_start_delay)))
                # np.ceil does what we want above, but float errors can miss the
                # equality:
                if self.ai_start_delay + (i_start - 1) / rate - t_start > -2e-16:
                    i_start -= 1
                # We want np.floor(x) to yield the largest integer < x (not <=):
                if t_end - self.ai_start_delay - i_end / rate < 2e-16:
                    i_end -= 1
                t_i = self.ai_start_delay + i_start / rate
                t_f = self.ai_start_delay + i_end / rate
                times = np.linspace(t_i, t_f, i_end - i_start + 1, endpoint=True)
                values = self.buffered_data[connection][i_start : i_end + 1]
                dtypes = [('t', np.float64), ('values', np.float32)]
                data = np.empty(len(values), dtype=dtype_workaround(dtypes))
                data['t'] = times
                data['values'] = values
                measurements.create_dataset(label, data=data)

    def abort_buffered(self):
        # TODO: test this
        return self.transition_to_manual(True)

    def abort_transition_to_buffered(self):
        # TODO: test this
        return self.transition_to_manual(True)

    def program_manual(self, values):
        return {}
