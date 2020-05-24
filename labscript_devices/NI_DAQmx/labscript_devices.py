#####################################################################
#                                                                   #
# /NI_DAQmx/models/labscript_devices.py                             #
#                                                                   #
# Copyright 2018, Monash University, JQI, Christopher Billington    #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################

__version__ = '1.0.0'


from labscript import (
    IntermediateDevice,
    AnalogOut,
    DigitalOut,
    StaticAnalogOut,
    StaticDigitalOut,
    AnalogIn,
    bitfield,
    config,
    compiler,
    LabscriptError,
    set_passed_properties,
)
from labscript_utils import dedent
from .utils import split_conn_DO, split_conn_AO, split_conn_AI
import numpy as np

_ints = {8: np.uint8, 16: np.uint16, 32: np.uint32, 64: np.uint64}


def _smallest_int_type(n):
    """Return the smallest unsigned integer type sufficient to contain n bits"""
    return _ints[min(size for size in _ints.keys() if size >= n)]


class NI_DAQmx(IntermediateDevice):
    # Will be overridden during __init__ depending on configuration:
    allowed_children = []

    description = 'NI-DAQmx'

    # If used as a wait monitor, this device's BLACS worker supports posting events in
    # software indicating the completion of each wait as it occurs:
    wait_monitor_supports_wait_completed_events = True

    @set_passed_properties(
        property_names={
            "connection_table_properties": [
                "clock_terminal",
                "MAX_name",
                "static_AO",
                "static_DO",
                "clock_mirror_terminal",
                "AI_range",
                "AI_start_delay",
                "AO_range",
                "max_AI_multi_chan_rate",
                "max_AI_single_chan_rate",
                "max_AO_sample_rate",
                "max_DO_sample_rate",
                "min_semiperiod_measurement",
                "num_AI",
                "num_AO",
                "num_CI",
                "ports",
                "supports_buffered_AO",
                "supports_buffered_DO",
                "supports_semiperiod_measurement",
                "clock_limit",
                "wait_monitor_minimum_pulse_width",
                "wait_monitor_supports_wait_completed_events",
            ],
            "device_properties": ["acquisition_rate"],
        }
    )
    def __init__(
        self,
        name,
        parent_device=None,
        clock_terminal=None,
        MAX_name=None,
        static_AO=None,
        static_DO=None,
        clock_mirror_terminal=None,
        acquisition_rate=None,
        AI_range=None,
        AI_start_delay=0,
        AO_range=None,
        max_AI_multi_chan_rate=None,
        max_AI_single_chan_rate=None,
        max_AO_sample_rate=None,
        max_DO_sample_rate=None,
        min_semiperiod_measurement=None,
        num_AI=0,
        num_AO=0,
        num_CI=0,
        ports=None,
        supports_buffered_AO=False,
        supports_buffered_DO=False,
        supports_semiperiod_measurement=False,
        **kwargs
    ):
        """Generic class for NI_DAQmx devices."""

        # Default static output setting based on whether the device supports buffered
        # output:
        if static_AO is None:
            static_AO = not supports_buffered_AO
        if static_DO is None:
            static_DO = not supports_buffered_DO

        # Parent is only allowed to be None if output is static:
        if parent_device is None and not (static_DO and static_AO):
            msg = """Must specify a parent clockline, unless both static_AO and
                static_DO are True"""
            raise LabscriptError(dedent(msg))
        # If parent device is not None though, then clock terminal must be specified:
        if parent_device is not None and clock_terminal is None:
            msg = """If parent_device is given, then clock_terminal must be specified as
                well as the terminal to which the parent pseudoclock is connected."""
            raise ValueError(dedent(msg))
        if acquisition_rate is not None and num_AI == 0:
            msg = "Cannot set set acquisition rate on device with no analog inputs"
            raise ValueError(msg)
        # Acquisition rate cannot be larger than the single channel rate:
        if acquisition_rate is not None and acquisition_rate > max_AI_single_chan_rate:
            msg = """acquisition_rate %f is larger than the maximum single-channel rate
                %f for this device"""
            raise ValueError(dedent(msg) % (acquisition_rate, max_AI_single_chan_rate))

        self.clock_terminal = clock_terminal
        self.MAX_name = MAX_name if MAX_name is not None else name
        self.static_AO = static_AO
        self.static_DO = static_DO

        self.acquisition_rate = acquisition_rate
        self.AO_range = AO_range
        self.max_AI_multi_chan_rate = max_AI_multi_chan_rate
        self.max_AI_single_chan_rate = max_AI_single_chan_rate
        self.max_AO_sample_rate = max_AO_sample_rate
        self.max_DO_sample_rate = max_DO_sample_rate
        self.min_semiperiod_measurement = min_semiperiod_measurement
        self.num_AI = num_AI
        self.num_AO = num_AO
        self.num_CI = num_CI
        self.ports = ports if ports is not None else {}
        self.supports_buffered_AO = supports_buffered_AO
        self.supports_buffered_DO = supports_buffered_DO
        self.supports_semiperiod_measurement = supports_semiperiod_measurement

        if self.supports_buffered_DO and self.supports_buffered_AO:
            self.clock_limit = min(self.max_DO_sample_rate, self.max_AO_sample_rate)
        elif self.supports_buffered_DO:
            self.clock_limit = self.max_DO_sample_rate
        elif self.supports_buffered_AO:
            self.clock_limit = self.max_AO_sample_rate
        else:
            self.clock_limit = None
            if not (static_AO and static_DO):
                msg = """Device does not support buffered output, please instantiate
                it with static_AO=True and static_DO=True"""
                raise LabscriptError(dedent(msg))

        self.wait_monitor_minimum_pulse_width = self.min_semiperiod_measurement

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

        if clock_terminal is None and not (static_AO and static_DO):
            msg = """Clock terminal must be specified unless static_AO and static_DO are
                both True"""
            raise LabscriptError(dedent(msg))

        self.BLACS_connection = self.MAX_name

        # Cannot be set with set_passed_properties because of name mangling with the
        # initial double underscore:
        self.set_property('__version__', __version__, 'connection_table_properties')

        # This is called late since it must be called after our clock_limit attribute is
        # set:
        IntermediateDevice.__init__(self, name, parent_device, **kwargs)

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
            ao_num = split_conn_AO(device.connection)
            if ao_num >= self.num_AO:
                msg = """Cannot add output with connection string '%s' to device with
                num_AO=%d"""
                raise ValueError(dedent(msg) % (device.connection, self.num_AO))
        elif isinstance(device, (DigitalOut, StaticDigitalOut)):
            port, line = split_conn_DO(device.connection)
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
            ai_num = split_conn_AI(device.connection)
            if ai_num >= self.num_AI:
                msg = """Cannot add analog input with connection string '%s' to device
                with num_AI=%d"""
                raise ValueError(dedent(msg) % (device.connection, self.num_AI))
            if self.acquisition_rate is None:
                msg = """Cannot add analog input to NI_DAQmx device with
                    acquisition_rate=None. Please set acquisition_rate as an
                    instantiation argument to the parent NI_DAQmx device."""
                raise ValueError(dedent(msg))
            if self.parent_device is None:
                msg = """Cannot add analog input to device with no parent pseudoclock.
                    Even if there is no buffered output, a pseudoclock is still required
                    to trigger the start of acquisition. Please specify a parent_device
                    and clock_terminal for device %s"""
                raise ValueError(dedent(msg) % self.name)

        IntermediateDevice.add_device(self, device)

    def _check_even_children(self, analogs, digitals):
        """Check that there are an even number of children of each type."""
        errmsg = """{0} {1} must have an even number of {2}s in order to guarantee an
            even total number of samples, which is a limitation of the DAQmx library.
            Please add a dummy {2} device or remove one you're not using, so that there
            is an even number."""
        if len(analogs) % 2:
            msg = errmsg.format(self.description, self.name, 'analog output')
            raise LabscriptError(dedent(msg))
        if len(digitals) % 2:
            msg = errmsg.format(self.description, self.name, 'digital output')
            raise LabscriptError(dedent(msg))

    def _check_bounds(self, analogs):
        """Check that all analog outputs are in bounds"""
        if not analogs:
            return
        vmin, vmax = self.AO_range
        # Floating point rounding error can produce values that would mathematically be
        # within bounds, but have ended up numerically out of bounds. We allow
        # out-of-bounds values within a small threshold through, but apply clipping to
        # keep them numerically within bounds. 1e-10 of the total range corresponds to >
        # 32 bits of precision, so this is not changing the voltages at all since none
        # of the DACs are that precise.
        eps = abs(vmax - vmin) * 1e-10
        for output in analogs.values():
            if any((output.raw_output < vmin - eps) | (output.raw_output > vmax + eps)):
                msg = """%s %s can only have values between %e and %e Volts, the limit
                    imposed by %s."""
                msg = msg % (output.description, output.name, vmin, vmax, self.name)
                raise LabscriptError(dedent(msg))
            np.clip(output.raw_output, vmin, vmax, out=output.raw_output)

    def _check_AI_not_too_fast(self, AI_table):
        if AI_table is None:
            return
        n = len(set(AI_table['connection']))
        if n < 2:
            # Either no AI in use, or already checked against single channel rate in
            # __init__.
            return
        if self.acquisition_rate <= self.max_AI_multi_chan_rate / n:
            return
        msg = """Requested acqusition_rate %f for device %s with %d analog input
            channels in use is too fast. Device supports a rate of %f per channel when
            multiple channels are in use."""
        msg = msg % (self.acquisition_rate, self.name, n, self.max_AI_multi_chan_rate)
        raise ValueError(dedent(msg))

    def _make_analog_out_table(self, analogs, times):
        """Collect analog output data and create the output array"""
        if not analogs:
            return None
        n_timepoints = 1 if self.static_AO else len(times)
        connections = sorted(analogs, key=split_conn_AO)
        dtypes = [(c, np.float32) for c in connections]
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
            port, line = split_conn_DO(connection)
            port_str = 'port%d' % port
            if port not in bits_by_port:
                # Make a list of the right size for the number of lines
                # on the port, or the number of bits in the smallest integer
                # type that is equal to or larger than the number of lines.
                nlines = self.ports[port_str]["num_lines"]
                int_type = _smallest_int_type(nlines)
                int_type_nbits = 8 * int_type().nbytes
                columns[port] = (port_str, int_type)
                bits_by_port[port] = [0] * int_type_nbits
            bits_by_port[port][line] = output.raw_output
        dtypes = [columns[port] for port in sorted(columns)]
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
        if acquisitions and compiler.wait_table and compiler.wait_monitor is None:
            msg = """Cannot do analog input on an NI DAQmx device in an experiment that
                uses waits without a wait monitor. This is because input data cannot be
                'chunked' into requested segments without knowledge of the durations of
                the waits. See labscript.WaitMonitor for details."""
            raise LabscriptError(dedent(msg))

        # The 'a256' dtype below limits the string fields to 256
        # characters. Can't imagine this would be an issue, but to not
        # specify the string length (using dtype=str) causes the strings
        # to all come out empty.
        acquisitions_table_dtypes = [
            ('connection', 'a256'),
            ('label', 'a256'),
            ('start', float),
            ('stop', float),
            ('wait label', 'a256'),
            ('scale factor', float),
            ('units', 'a256'),
        ]
        acquisition_table = np.empty(len(acquisitions), dtype=acquisitions_table_dtypes)
        for i, acq in enumerate(acquisitions):
            acquisition_table[i] = acq

        return acquisition_table

    def _check_wait_monitor_timeout_device_config(self):
        """Check that if we are the wait monitor acquisition device and another device
        is the wait monitor timeout device, that a) the other device is a DAQmx device
        and b) the other device has a start_order lower than us and a stop_order higher
        than us."""
        if compiler.wait_monitor is None:
            return
        acquisition_device = compiler.wait_monitor.acquisition_device
        timeout_device = compiler.wait_monitor.timeout_device
        if acquisition_device is not self or timeout_device is None:
            return
        if timeout_device is self:
            return
        if not isinstance(timeout_device, NI_DAQmx):
            msg = """If using an NI DAQmx device as a wait monitor acquisition device,
                then the wait monitor timeout device must also be an NI DAQmx device,
                not {}."""
            raise TypeError(dedent(msg).format(type(timeout_device)))
        timeout_start = timeout_device.start_order
        if timeout_start is None:
            timeout_start = 0
        timeout_stop = timeout_device.stop_order
        if timeout_stop is None:
            timeout_stop = 0
        self_start = self.start_order
        if self_start is None:
            self_start = 0
        self_stop = self.stop_order
        if self_stop is None:
            self_stop = 0
        if timeout_start >= self_start or timeout_stop <= self_stop:
            msg = """If using different DAQmx devices as the wait monitor acquisition
                and timeout devices, the timeout device must transition_to_buffered
                before the acquisition device, and transition_to_manual after it, in
                order to ensure the output port for timeout pulses is not in use (by the
                manual mode DO task) when the wait monitor subprocess attempts to use
                it. To achieve this, pass the start_order and stop_order keyword
                arguments to the devices in your connection table, ensuring that the
                timeout device has a lower start_order and a higher stop_order than the
                acquisition device. The default start_order and stop_order is zero, so
                if you are not otherwise controlling the order that devices are
                programmed, you can set start_order=-1, stop_order=1 on the timeout
                device only."""
            raise RuntimeError(dedent(msg))

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

        clockline = self.parent_device
        if clockline is None:
            # No pseudoclock to call expand_timeseries() on our children.
            # Call it ourselves:
            for device in self.child_devices:
                if isinstance(device, (StaticDigitalOut, StaticAnalogOut)):
                    device.expand_timeseries()
            times = None
        else:
            times = clockline.parent_device.times[clockline]

        self._check_even_children(analogs, digitals)
        self._check_bounds(analogs)

        AO_table = self._make_analog_out_table(analogs, times)
        DO_table = self._make_digital_out_table(digitals, times)
        AI_table = self._make_analog_input_table(inputs)

        self._check_AI_not_too_fast(AI_table)
        self._check_wait_monitor_timeout_device_config()

        grp = self.init_device_group(hdf5_file)
        if AO_table is not None:
            grp.create_dataset('AO', data=AO_table, compression=config.compression)
        if DO_table is not None:
            grp.create_dataset('DO', data=DO_table, compression=config.compression)
        if AI_table is not None:
            grp.create_dataset('AI', data=AI_table, compression=config.compression)


from .models import *
