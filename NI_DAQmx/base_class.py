#####################################################################
#                                                                   #
# /NI_DAQmx/base_class.py                                           #
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

import os
from labscript import (
    IntermediateDevice,
    AnalogOut,
    DigitalOut,
    StaticAnalogOut,
    StaticDigitalOut,
    AnalogIn,
    bitfield,
    config,
    LabscriptError,
    set_passed_properties,
)
from labscript_utils.numpy_dtype_workaround import dtype_workaround

import numpy as np

_ints = {8: np.uint8, 16: np.uint16, 32: np.uint32, 64: np.uint64}


def dedent(s):
    return ' '.join(s.split())


def _smallest_int_type(n):
    """Return the smallest unsigned integer type sufficient to contain n bits"""
    return _ints[min(size for size in _ints.keys() if size >= n)]


def _split_conn_DO(connection):
    """Return the port and line number of a connection string such as 'port0/line1
    as two integers, or raise ValueError if format is invalid"""
    try:
        port, line = [int(n) for n in connection.split('port', 1)[1].split('/line')]
    except (ValueError, IndexError):
        msg = """Digital output connection string %s does not match format
            'port<N>/line<M>' for integers N, M"""
        raise ValueError(dedent(msg) % str(connection))
    return port, line


def _split_conn_AO(connection):
    """Return analog output number of a connection string such as 'ao1' as an
    integer, or raise ValueError if format is invalid"""
    try:
        return int(connection.split('ao', 1)[1])
    except (ValueError, IndexError):
        msg = """Analog output connection string %s does not match format 'ao<N>' for
            integer N"""
        raise ValueError(dedent(msg) % str(connection))


def _split_conn_AI(connection):
    """Return analog input number of a connection string such as 'ai1' as an
    integer, or raise ValueError if format is invalid"""
    try:
        return int(connection.split('ai', 1)[1])
    except (ValueError, IndexError):
        msg = """Analog input connection string %s does not match format 'ai<N>' for
            integer N"""
        raise ValueError(dedent(msg) % str(connection))


def _split_conn_PFI(connection):
    """Return PFI input number of a connection string such as 'PFI0' as an
    integer, or raise ValueError if format is invalid"""
    try:
        return int(connection.split('PFI', 1)[1])
    except (ValueError, IndexError):
        msg = "PFI connection string %s does not match format 'PFI<N>' for integer N"
        raise ValueError(msg % str(connection))


class NI_DAQmx(IntermediateDevice):
    # Will be overridden during __init__ depending on configuration:
    allowed_children = []

    description = 'NI-DAQmx'

    @set_passed_properties(
        property_names={
            "connection_table_properties": [
                "clock_terminal",
                "static_AO",
                "static_DO",
                "DAQmx_waits_counter_bug_workaround",
                "clock_mirror_terminal",
                "AO_ranges",
                "max_AI_multi_chan_rate",
                "max_AI_single_chan_rate",
                "max_AO_sample_rate",
                "max_DO_sample_rate",
                "num_AI",
                "num_AO",
                "num_CI",
                "ports",
                "supports_buffered_AO",
                "supports_buffered_DO",
            ],
            "device_properties": ["acquisition_rate"],
        }
    )
    def __init__(
        self,
        name,
        parent_device,
        model,
        clock_terminal=None,
        MAX_name=None,
        static_AO=False,
        static_DO=False,
        DAQmx_waits_counter_bug_workaround=False,
        clock_mirror_terminal=None,
        acquisition_rate=None,
        AO_ranges=None,
        max_AI_multi_chan_rate=None,
        max_AI_single_chan_rate=None,
        max_AO_sample_rate=None,
        max_DO_sample_rate=None,
        num_AI=0,
        num_AO=0,
        num_CI=0,
        ports=None,
        supports_buffered_AO=False,
        supports_buffered_DO=False,
        **kwargs
    ):
        """Generic class for NI_DAQmx devices. Reads capabilities from a file
        that stores the capabilities of known devices."""

        if clock_terminal is None and not (static_AO and static_DO):
            msg = """Clock terminal must be specified unless static_AO and static_AO are
                both True"""
            raise LabscriptError(dedent(msg))

        self.model = model
        self.static_AO = static_AO
        self.static_DO = static_DO
        self.clock_terminal = clock_terminal
        self.MAX_name = MAX_name if MAX_name is not None else name
        self.acquisition_rate = acquisition_rate

        self.num_AO = num_AO
        self.num_AI = num_AI
        self.ports = ports if ports is not None else {}
        self.num_CI = num_CI
        self.supports_buffered_AO = supports_buffered_AO
        self.supports_buffered_DO = supports_buffered_DO
        self.max_AI_multi_chan_rate = max_AI_multi_chan_rate
        self.max_AI_single_chan_rate = max_AI_single_chan_rate
        self.max_AO_sample_rate = max_AO_sample_rate
        self.max_DO_sample_rate = max_DO_sample_rate

        if self.supports_buffered_DO and self.supports_buffered_AO:
            self.clock_limit = min(self.max_DO_sample_rate, self.max_AO_sample_rate)
        elif self.supports_buffered_DO:
            self.clock_limit = self.max_DO_sample_rate
        elif self.supports_buffered_AO:
            self.clock_limit = self.max_AO_sample_rate
        else:
            if not (static_AO and static_DO):
                msg = """Device does not support buffered output, please instantiate
                it with static_AO=True and static_DO=True"""
                raise LabscriptError(dedent(msg))

        # Set allowed children based on capabilities:
        self.allowed_children = []
        if self.num_AI > 0:
            self.allowed_children += [AnalogIn]
        if self.num_AO > 0 and static_AO:
            self.allowed_children += [StaticAnalogOut]
        if self.num_AO > 0 and not static_AO:
            self.allowed_children += [AnalogOut]
        if self.ports and static_DO:
            self.allowed_children += [StaticDigitalOut]
        if self.ports and not static_DO:
            self.allowed_children += [DigitalOut]

        if self.num_AO > 0:
            # capabilities["AO_ranges"] is a list of 2-element lists Vmin, Vmax. Get the
            # smallest Vmin and largest Vmax:
            Vmin = min([r[0] for r in AO_ranges])
            Vmax = max([r[1] for r in AO_ranges])
            self.range_AO = Vmin, Vmax
        else:
            self.range_AO = None

        self.BLACS_connection = self.MAX_name

        # This is to instruct the wait monitor device to:
        # a) in labscript compilation: Use an 0.1 second duration for the wait monitor
        #    trigger instead of a shorter one
        # b) In the BLACS waits worker process: skip the initial rising edge. These are
        #    to work around what seems to be a bug in DAQmx. The initial rising edge is
        #    not supposed to be detected, and clearly pulses of less than 0.1 seconds
        #    ought to be detectable. However this workaround fixes things for the
        #    affected devices, currenly the NI USB 6229 on NI DAQmx 15.0.
        self.DAQmx_waits_counter_bug_workaround = DAQmx_waits_counter_bug_workaround

        # This is called late since it must be called after our clock_limit attribute is
        # set:
        IntermediateDevice.__init__(self, name, parent_device)

    def add_device(self, device):
        """Error checking for adding a child device"""
        # Verify static/dynamic outputs compatible with configuration:
        if isinstance(device, StaticAnalogOut) and not self.static_AO:
            msg = """Cannot add StaticAnalogOut to NI_DAQmx device configured for
                dynamic analog output. Pass static_AO=True for static analog output"""
            raise LabscriptError(dedent(msg))
        if isinstance(device, StaticDigitalOut) and not self.static_DO:
            msg = """Cannot add StaticDigitalOut to NI_DAQmx device configured for
                dynamic digital output. Pass static_DO=True for static digital output"""
            raise LabscriptError(dedent(msg))
        if isinstance(device, AnalogOut) and self.static_AO:
            msg = """Cannot add AnalogOut to NI_DAQmx device configured for
                static analog output. Pass static_AO=False for dynamic analog output"""
            raise LabscriptError(dedent(msg))
        if isinstance(device, DigitalOut) and self.static_DO:
            msg = """Cannot add DigitalOut to NI_DAQmx device configured for static
                digital output. Pass static_DO=False for dynamic digital output"""
            raise LabscriptError(dedent(msg))
        # Verify connection string is OK:
        if isinstance(device, (AnalogOut, StaticAnalogOut)):
            ao_num = _split_conn_AO(device.connection)
            if ao_num >= self.num_AO:
                msg = """Cannot add output with connection string '%s' to device with
                num_AO=%d"""
                raise ValueError(dedent(msg) % (device.connection, self.num_AO))
        elif isinstance(device, (DigitalOut, StaticDigitalOut)):
            port, line = _split_conn_DO(device.connection)
            port_str = 'port%d' % port
            if port_str not in self.ports:
                msg = "Parent device has no such DO port '%s'" % port_str
                raise ValueError(msg)
            nlines = self.ports[port_str]['num_lines']
            if line >= nlines:
                msg = """Canot add output with connection string '%s' to port '%s'
                with only %d lines"""
                raise ValueError(dedent(msg) % (device.connection, port_str, nlines))
            supports_buffered = self.ports[port_str]['supports_buffered']
            if isinstance(device, DigitalOut) and not supports_buffered:
                msg = """Cannot add DigitalOut port '%s', which does not support
                    buffered output"""
                raise ValueError(dedent(msg) % port_str)
        elif isinstance(device, AnalogIn):
            ai_num = _split_conn_AI(device.connection)
            if ai_num >= self.num_AI:
                msg = """Cannot add input with connection string '%s' to device with
                num_AI=%d"""
                raise ValueError(dedent(msg) % (device.connection, self.num_AI))

        IntermediateDevice.add_device(self, device)

    def _check_even_children(self, analogs, digitals, inputs):
        """Check that there are an even number of children of each type."""
        errmsg = """{0} {1} must have an even numer of {2}s in order to guarantee an
            even total number of samples, which is a limitation of the DAQmx library.
            Please add a dummy {2} device or remove one you're not using, so that there
            are an even number."""
        if len(analogs) % 2:
            msg = errmsg.format(self.description, self.name, 'analog output')
            raise LabscriptError(dedent(msg))
        if len(digitals) % 2:
            msg = errmsg.format(self.description, self.name, 'digital output')
            raise LabscriptError(dedent(msg))
        if len(inputs) % 2:
            msg = errmsg.format(self.description, self.name, 'analog input')
            raise LabscriptError(dedent(msg))

    def _check_bounds(self, analogs):
        """Check that all analog outputs are in bounds"""
        vmin, vmax = self.range_AO
        for output in analogs.values():
            if any((output.raw_output < vmin) | (output.raw_output > vmax)):
                msg = """%s %s ' % (output.description, output.name) can only have
                    values between %e and %e Volts the limit imposed by %s."""
                msg = msg % (output.description, output.name, vmin, vmax, self.name)
                raise LabscriptError(dedent(msg))

    def _check_digitals_do_something(self, DO_table):
        """Check that digital outs are not all zero all the time."""
        if DO_table is None:
            return
        for port in DO_table.dtype.names:
            if DO_table[port].sum() > 0:
                return
        msg = """digital outs being all zero for the entire experiment triggers a bug in
            NI-DAQmx that prevents experiments from running. Please ensure at least one
            digital out is nonzero at some time."""
        raise LabscriptError(dedent(msg))

    def _make_analog_out_table(self, analogs, times):
        """Collect analog output data and create the output array"""
        if not analogs:
            return None
        n_timepoints = 1 if self.static_AO else len(times)
        connections = sorted(analogs, key=_split_conn_AO)
        dtypes = dtype_workaround([(c, np.float32) for c in connections])
        analog_out_table = np.empty(n_timepoints, dtype=dtypes)
        for connection, output in analogs.items():
            analog_out_table[connection] = output.raw_output
        return analog_out_table

    def _make_digital_out_table(self, digitals, times):
        """Collect digital output data and create the output array"""
        if not digitals:
            return None
        n_timepoints = 1 if self.static_DO else len(times)
        # List of output bits by port number:
        bits_by_port = {}
        # table names and dtypes by port number:
        columns = {}
        for connection, output in digitals.items():
            port, line = _split_conn_DO(connection)
            port_str = 'port%d' % port
            if port not in bits_by_port:
                nlines = self.ports[port_str]["num_lines"]
                bits_by_port[port] = [0] * nlines
                columns[port] = (port_str, _smallest_int_type(nlines))
            bits_by_port[port][line] = output.raw_output
        dtypes = dtype_workaround([columns[port] for port in sorted(columns)])
        digital_out_table = np.empty(n_timepoints, dtype=dtypes)
        for port, bits in bits_by_port.items():
            # Pack the bits from each port into an integer:
            port_str, dtype = columns[port]
            values = bitfield(bits, dtype=dtype)
            # Put them into the table:
            digital_out_table[port_str] = np.array(values)
        return digital_out_table

    def _make_analog_input_table(self, inputs):
        """Collect analog input instructions and create the acquisition table"""
        if not inputs:
            return None
        acquisitions = []
        for connection, input in inputs.items():
            for acq in input.acquisitions:
                acquisitions.append(
                    (
                        connection,
                        acq['label'],
                        acq['start_time'],
                        acq['end_time'],
                        acq['wait_label'],
                        acq['scale_factor'],
                        acq['units'],
                    )
                )
        # The 'a256' dtype below limits the string fields to 256
        # characters. Can't imagine this would be an issue, but to not
        # specify the string length (using dtype=str) causes the strings
        # to all come out empty.
        acquisitions_table_dtypes = dtype_workaround(
            [
                ('connection', 'a256'),
                ('label', 'a256'),
                ('start', float),
                ('stop', float),
                ('wait label', 'a256'),
                ('scale factor', float),
                ('units', 'a256'),
            ]
        )
        acquisition_table = np.empty(len(acquisitions), dtype=acquisitions_table_dtypes)
        for i, acq in enumerate(acquisitions):
            acquisition_table[i] = acq

        return acquisition_table

    def generate_code(self, hdf5_file):
        IntermediateDevice.generate_code(self, hdf5_file)
        analogs = {}
        digitals = {}
        inputs = {}
        for device in self.child_devices:
            if isinstance(device, (AnalogOut, StaticAnalogOut)):
                analogs[device.connection] = device
            elif isinstance(device, (DigitalOut, StaticDigitalOut)):
                digitals[device.connection] = device
            elif isinstance(device, AnalogIn):
                inputs[device.connection] = device
            else:
                raise TypeError(device)

        self._check_even_children(analogs, digitals, inputs)
        self._check_bounds(analogs)

        clockline = self.parent_device
        pseudoclock = clockline.parent_device
        times = pseudoclock.times[clockline]

        AO_table = self._make_analog_out_table(analogs, times)
        DO_table = self._make_digital_out_table(digitals, times)
        AI_table = self._make_analog_input_table(inputs)

        self._check_digitals_do_something(DO_table)

        grp = self.init_device_group(hdf5_file)
        if AO_table is not None:
            grp.create_dataset('AO', data=AO_table, compression=config.compression)
        if DO_table is not None:
            grp.create_dataset('DO', data=DO_table, compression=config.compression)
        if AI_table is not None:
            grp.create_dataset('AI', data=AI_table, compression=config.compression)
