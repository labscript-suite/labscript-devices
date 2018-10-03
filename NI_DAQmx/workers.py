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

import numpy as np

import labscript_utils.h5_lock
import h5py

from PyDAQmx import *
from PyDAQmx.DAQmxConstants import *
from PyDAQmx.DAQmxTypes import *

from blacs.tab_base_classes import Worker


class Ni_DAQmxWorker(Worker):
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

        if self.DO_ports or self.num_PFI > 0:
            num_DO = sum(self.DO_ports.values())
            self.DO_task = Task()
            self.DO_data = np.zeros(num_DO + self.num_PFI, dtype=np.uint8)
        else:
            self.DO_task = None

        # Setup AO channels
        for i in range(self.num_AO):
            con = self.MAX_name + "/ao%d" % i
            self.AO_task.CreateAOVoltageChan(
                con, "", self.Vmin, self.Vmax, DAQmx_Val_Volts, None
            )

        # Setup DO channels:
        for port_str in sorted(self.DO_ports):
            con = '%s/%s' % (self.MAX_name, port_str)
            self.DO_task.CreateDOChan(con, "", DAQmx_Val_ChanForAllLines)

        # Setup PFI channels:
        if self.num_PFI > 0:
            con = '%s/PFI0:%d' % (self.MAX_name, self.num_PFI)
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
        i = 0
        for port_str, num_DO in sorted(self.DO_ports.items()):
            for j in range(num_DO):
                self.DO_data[i + j] = front_panel_values['%s/line%d' % (port_str, j)]
            i += num_DO
        for j in range(self.num_PFI):
            self.DO_data[i + j] = front_panel_values['PFI%d' % j]
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
            for line in self.DO_ports[port_str]:
                # Extract each digital value from the packed bits:
                line_final_value = bool((1 << line) & port_final_value)
                final_values['%s/line%d' % (port_str, line)] = int(line_final_value)

        # Methods for writing data to the task depending on the datatype of each port:
        write_methods = {
            np.uint8: self.DO_task.DAQmxWriteDigitalU8,
            np.uint16: self.DO_task.DAQmxWriteDigitalU16,
            np.uint32: self.DO_task.DAQmxWriteDigitalU32,
        }

        if self.static_DO:
            # Static DO. Start the task and write data, no timing configuration.
            self.DO_task.StartTask()
            # Write data for each port:
            for port_str in ports:
                data = DO_table[port_str][0]
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
        final_values = dict(AO_table[-1])

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
                ao_data.shape[0],
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
        current_pos = uInt64()
        total_samples = uInt64()
        if self.AO_task is not None:
            if not abort:
                if not self.static_AO:
                    # Log current position in output array:
                    self.AO_task.GetWriteCurrWritePos(byref(current_pos))
                    self.AO_task.GetWriteTotalSampPerChanGenerated(byref(total_samples))
                    msg = 'Stopping AO at sample %d of %d'
                    self.logger.debug(msg, current_pos.value, total_samples.value)
                self.AO_task.StopTask()
            self.AO_task.ClearTask()
            self.AO_task = None

        if self.DO_task is not None:
            if not abort:
                if not self.static_DO:
                    # Log current position in output array:
                    self.DO_task.GetWriteCurrWritePos(byref(current_pos))
                    self.DO_task.GetWriteTotalSampPerChanGenerated(byref(total_samples))
                    msg = 'Stopping DO at sample %d of %d'
                    self.logger.debug(msg, current_pos.value, total_samples.value)
                self.DO_task.StopTask()
            self.DO_task.ClearTask()
            self.DO_task = None

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
