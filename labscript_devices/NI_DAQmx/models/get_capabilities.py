#####################################################################
#                                                                   #
# /NI_DAQmx/models/get_capabilities.py                              #
#                                                                   #
# Copyright 2018, Christopher Billington                            #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################

import numpy as np
import os
import ctypes
import json
import PyDAQmx
from PyDAQmx import byref, Task
from PyDAQmx.DAQmxTypes import uInt32, bool32, int32, float64
import PyDAQmx.DAQmxConstants as c

THIS_FOLDER = os.path.dirname(os.path.abspath(__file__))
CAPABILITIES_FILE = os.path.join(THIS_FOLDER, 'capabilities.json')


"""This is a script to update model_capabilities.json with the capabilities of all
NI-DAQmx devices currently connected to this computer. Run this script to add support
for a new model of NI-DAQmx device. Note that this will work with a simulated device
configured through NI-MAX as well, so support can be added without actually having the
physical device"""


def string_prop(func):
    def wrapped(name=None):
        BUFSIZE = 4096
        result = ctypes.create_string_buffer(BUFSIZE)
        if name is None:
            func(result, uInt32(BUFSIZE))
        else:
            func(name, result, uInt32(BUFSIZE))
        return result.value.decode('utf8')

    return wrapped


def bool_prop(func):
    def wrapped(name):
        result = bool32()
        func(name, byref(result))
        return bool(result.value)

    return wrapped


def int32_prop(func):
    def wrapped(name):
        result = int32()
        func(name, byref(result))
        return result.value

    return wrapped


def float64_prop(func):
    def wrapped(name):
        result = float64()
        func(name, byref(result))
        return result.value

    return wrapped


def float64_array_prop(func):
    def wrapped(name):
        import warnings

        with warnings.catch_warnings():
            # PyDAQmx warns about a positive return value, but actually this is how you
            # are supposed to figure out the size of the array required.
            warnings.simplefilter("ignore")
            # Pass in null pointer and 0 len to ask for what array size is needed:
            npts = func(name, byref(float64()), 0)
        # Create that array
        result = (float64 * npts)()
        func(name, result, npts)
        result = [result[i] for i in range(npts)]
        return result

    return wrapped


def chans(func):
    """string_prop but splitting the return value into separate channels and stripping
    the device name from them"""
    wrapped1 = string_prop(func)

    def wrapped2(name):
        result = wrapped1(name)
        if result:
            return [s.strip('/').split('/', 1)[1] for s in result.split(', ')]
        return []

    return wrapped2


DAQmxGetSysDevNames = string_prop(PyDAQmx.DAQmxGetSysDevNames)
DAQmxGetDevProductType = string_prop(PyDAQmx.DAQmxGetDevProductType)
DAQmxGetDevAnlgTrigSupported = bool_prop(PyDAQmx.DAQmxGetDevAnlgTrigSupported)
DAQmxGetDevDigTrigSupported = bool_prop(PyDAQmx.DAQmxGetDevDigTrigSupported)
DAQmxGetDevAOSampClkSupported = bool_prop(PyDAQmx.DAQmxGetDevAOSampClkSupported)
DAQmxGetDevAOPhysicalChans = chans(PyDAQmx.DAQmxGetDevAOPhysicalChans)
DAQmxGetDevAIPhysicalChans = chans(PyDAQmx.DAQmxGetDevAIPhysicalChans)
DAQmxGetDevDOPorts = chans(PyDAQmx.DAQmxGetDevDOPorts)
DAQmxGetDevDOLines = chans(PyDAQmx.DAQmxGetDevDOLines)
DAQmxGetDevDIPorts = chans(PyDAQmx.DAQmxGetDevDIPorts)
DAQmxGetDevDILines = chans(PyDAQmx.DAQmxGetDevDILines)
DAQmxGetDevTerminals = chans(PyDAQmx.DAQmxGetDevTerminals)
DAQmxGetDevCIPhysicalChans = chans(PyDAQmx.DAQmxGetDevCIPhysicalChans)
DAQmxGetDevDOMaxRate = float64_prop(PyDAQmx.DAQmxGetDevDOMaxRate)
DAQmxGetDevAOMaxRate = float64_prop(PyDAQmx.DAQmxGetDevAOMaxRate)
DAQmxGetDevAIMaxSingleChanRate = float64_prop(PyDAQmx.DAQmxGetDevAIMaxSingleChanRate)
DAQmxGetDevAIMaxMultiChanRate = float64_prop(PyDAQmx.DAQmxGetDevAIMaxMultiChanRate)
DAQmxGetDevAOVoltageRngs = float64_array_prop(PyDAQmx.DAQmxGetDevAOVoltageRngs)
DAQmxGetDevAIVoltageRngs = float64_array_prop(PyDAQmx.DAQmxGetDevAIVoltageRngs)


def port_supports_buffered(device_name, port, clock_terminal=None):
    all_terminals = DAQmxGetDevTerminals(device_name)
    if clock_terminal is None:
        clock_terminal = all_terminals[0]
    npts = 16
    task = Task()
    clock_terminal_full = '/' + device_name + '/' + clock_terminal
    data = np.zeros(npts, dtype=np.uint32)
    task.CreateDOChan(device_name + "/" + port, "", c.DAQmx_Val_ChanForAllLines)
    task.CfgSampClkTiming(
        clock_terminal_full, 100, c.DAQmx_Val_Rising, c.DAQmx_Val_FiniteSamps, npts
    )
    written = int32()
    try:
        task.WriteDigitalU32(
            npts, False, 10.0, c.DAQmx_Val_GroupByScanNumber, data, byref(written), None
        )
    except (
        PyDAQmx.DAQmxFunctions.BufferedOperationsNotSupportedOnSelectedLinesError,
        PyDAQmx.DAQmxFunctions.PhysicalChanNotSupportedGivenSampTimingType653xError,
    ):
        return False
    except (
        PyDAQmx.DAQmxFunctions.CantUsePort3AloneGivenSampTimingTypeOn653xError,
        PyDAQmx.DAQmxFunctions.CantUsePort1AloneGivenSampTimingTypeOn653xError,
    ):
        # Ports that throw this error on 653x devices do support buffered output, though
        # there are requirements that multiple ports be used together.
        return True
    except PyDAQmx.DAQmxFunctions.RouteNotSupportedByHW_RoutingError:
        # Try again with a different terminal
        current_terminal_index = all_terminals.index(clock_terminal)
        if current_terminal_index == len(all_terminals) - 1:
            # There are no more terminals. No terminals can be used as clocks,
            # therefore we cannot do externally clocked buffered output.
            return False
        next_terminal_to_try = all_terminals[current_terminal_index + 1]
        return port_supports_buffered(device_name, port, next_terminal_to_try)
    else:
        return True
    finally:
        task.ClearTask()


def AI_start_delay(device_name):
    if 'PFI0' not in DAQmxGetDevTerminals(device_name):
        return None
    task = Task()
    clock_terminal = '/' + device_name + '/PFI0'
    rate = DAQmxGetDevAIMaxSingleChanRate(device_name)
    Vmin, Vmax = DAQmxGetDevAIVoltageRngs(device_name)[0:2]
    num_samples = 1000
    chan = device_name + '/ai0'
    task.CreateAIVoltageChan(
        chan, "", c.DAQmx_Val_RSE, Vmin, Vmax, c.DAQmx_Val_Volts, None
    )
    task.CfgSampClkTiming(
        "", rate, c.DAQmx_Val_Rising, c.DAQmx_Val_ContSamps, num_samples
    )
    task.CfgDigEdgeStartTrig(clock_terminal, c.DAQmx_Val_Rising)

    start_trig_delay = float64()
    delay_from_sample_clock = float64()
    sample_timebase_rate = float64()

    task.GetStartTrigDelay(start_trig_delay)
    task.GetDelayFromSampClkDelay(delay_from_sample_clock)
    task.GetSampClkTimebaseRate(sample_timebase_rate)

    task.ClearTask()

    total_delay_in_ticks = start_trig_delay.value + delay_from_sample_clock.value
    total_delay_in_seconds = total_delay_in_ticks / sample_timebase_rate.value
    return total_delay_in_seconds


def supported_AI_ranges_for_non_differential_input(device_name, AI_ranges):
    """Try AI ranges to see which are actually allowed for non-differential input, since
    the largest range may only be available for differential input, which we don't
    attempt to support (though we could with a little effort)"""
    chan = device_name + '/ai0'
    supported_ranges = []
    for Vmin, Vmax in AI_ranges:
        try:
            task = Task()
            task.CreateAIVoltageChan(
                chan, "", c.DAQmx_Val_RSE, Vmin, Vmax, c.DAQmx_Val_Volts, None
            )
            task.StartTask()
        except PyDAQmx.DAQmxFunctions.InvalidAttributeValueError as e:
            if 'DAQmx_AI_Min' in e.message or 'DAQmx_AI_Max' in e.message:
                # Not supported for non-differential input:
                continue
            raise
        finally:
            task.ClearTask()
        supported_ranges.append([Vmin, Vmax])

    return supported_ranges


def supports_semiperiod_measurement(device_name):
    import warnings

    with warnings.catch_warnings():
        # PyDAQmx warns about a positive return value, but actually this is how you are
        # supposed to figure out the size of the array required.
        warnings.simplefilter("ignore")
        # Pass in null pointer and 0 len to ask for what array size is needed:
        npts = PyDAQmx.DAQmxGetDevCISupportedMeasTypes(device_name, int32(), 0)
    # Create that array
    result = (int32 * npts)()
    PyDAQmx.DAQmxGetDevCISupportedMeasTypes(device_name, result, npts)
    return c.DAQmx_Val_SemiPeriod in [result[i] for i in range(npts)]


def get_min_semiperiod_measurement(device_name):
    """Depending on the timebase used, counter inputs can measure time intervals of
    various ranges. As a default, we pick a largish range - the one with the fastest
    timebase still capable of measuring 100 seconds, or the largest time interval if it
    is less than 100 seconds, and we save the smallest interval measurable with this
    timebase. Then labscript can ensure it doesn't make wait monitor pulses shorter than
    this. This should be a sensible default behaviour, though if the user has
    experiments considerably shorter or longer than 100 seconds, such that they want to
    use a different timebase, they may pass the min_semiperiod_measurement keyword
    argument into the DAQmx class, to tell labscript to make pulses some other duration
    compatible with the maximum wait time in their experiment. However, since there are
    software delays in timeouts of waits during a shot, any timed-out waits necessarily
    will last software timescales of up to ~100ms on a slow computer, preventing one
    from using very fast timebases with low-resolution counters if there is any
    possibility of timing out. For now (in the wait monitor worker class) we
    pessimistically add one second to the expected longest measurement to account for
    software delays. These decisions can be revisited if there is a need, do not
    hesitate to file an issue on bitbucket regarding this if it affects you."""
    CI_chans = DAQmxGetDevCIPhysicalChans(device_name)
    CI_chan = device_name + '/' + CI_chans[0]
    # Make a task with a semiperiod measurement
    task = Task()
    task.CreateCISemiPeriodChan(CI_chan, '', 1e-100, 1e100, c.DAQmx_Val_Seconds, "")
    try:
        task.StartTask()
    except PyDAQmx.DAQmxFunctions.CtrMinMaxError as e:
        # Parse the error to extract the allowed values:
        CI_ranges = []
        DT_MIN_PREFIX = "Value Must Be Greater Than:"
        DT_MAX_PREFIX = "Value Must Be Less Than:"
        error_lines = e.message.splitlines()
        for line in error_lines:
            if DT_MIN_PREFIX in line:
                dt_min = float(line.replace(DT_MIN_PREFIX, ''))
            if DT_MAX_PREFIX in line:
                dt_max = float(line.replace(DT_MAX_PREFIX, ''))
                CI_ranges.append([dt_min, dt_max])
    else:
        raise AssertionError("Can't figure out counter input ranges")
    finally:
        task.ClearTask()

    # Pick out the value we want. Either dtmin when dtmax is over 100, or the largest
    # dtmin if there is no dtmax over 100:
    for dtmin, dtmax in sorted(CI_ranges):
        if dtmax > 100:
            return dtmin
    return dtmin


capabilities = {}
if os.path.exists(CAPABILITIES_FILE):
    with open(CAPABILITIES_FILE) as f:
        try:
            capabilities = json.load(f)
        except ValueError:
            pass


models = []
for name in DAQmxGetSysDevNames().split(', '):
    model = DAQmxGetDevProductType(name)
    print("found device:", name, model)
    if model not in models:
        models.append(model)
    capabilities[model] = {}
    try:
        capabilities[model]["supports_buffered_AO"] = DAQmxGetDevAOSampClkSupported(
            name
        )
    except PyDAQmx.DAQmxFunctions.AttrNotSupportedError:
        capabilities[model]["supports_buffered_AO"] = False
    try:
        capabilities[model]["max_DO_sample_rate"] = DAQmxGetDevDOMaxRate(name)
        capabilities[model]["supports_buffered_DO"] = True
    except PyDAQmx.DAQmxFunctions.AttrNotSupportedError:
        capabilities[model]["max_DO_sample_rate"] = None
        capabilities[model]["supports_buffered_DO"] = False
    if capabilities[model]["supports_buffered_AO"]:
        capabilities[model]["max_AO_sample_rate"] = DAQmxGetDevAOMaxRate(name)
    else:
        capabilities[model]["max_AO_sample_rate"] = None

    capabilities[model]["num_AO"] = len(DAQmxGetDevAOPhysicalChans(name))
    capabilities[model]["num_AI"] = len(DAQmxGetDevAIPhysicalChans(name))
    if capabilities[model]["num_AI"] > 0:
        single_rate = DAQmxGetDevAIMaxSingleChanRate(name)
        multi_rate = DAQmxGetDevAIMaxMultiChanRate(name)
    else:
        single_rate = None
        multi_rate = None
    capabilities[model]["max_AI_single_chan_rate"] = single_rate
    capabilities[model]["max_AI_multi_chan_rate"] = multi_rate

    capabilities[model]["ports"] = {}
    ports = DAQmxGetDevDOPorts(name)
    chans = DAQmxGetDevDOLines(name)
    for port in ports:
        if '_' in port:
            # Ignore the alternate port names such as 'port0_32' that allow using two or
            # more ports together as a single, larger one:
            continue
        port_info = {}
        capabilities[model]["ports"][port] = port_info
        port_chans = [chan for chan in chans if chan.split('/')[0] == port]
        port_info['num_lines'] = len(port_chans)
        if capabilities[model]["supports_buffered_DO"]:
            port_info['supports_buffered'] = port_supports_buffered(name, port)
        else:
            port_info['supports_buffered'] = False

    capabilities[model]["num_CI"] = len(DAQmxGetDevCIPhysicalChans(name))
    supports_semiperiod = supports_semiperiod_measurement(name)
    capabilities[model]["supports_semiperiod_measurement"] = supports_semiperiod
    if capabilities[model]["num_CI"] > 0 and supports_semiperiod:
        min_semiperiod_measurement = get_min_semiperiod_measurement(name)
    else:
        min_semiperiod_measurement = None
    capabilities[model]["min_semiperiod_measurement"] = min_semiperiod_measurement

    if capabilities[model]['num_AO'] > 0:
        AO_ranges = []
        raw_limits = DAQmxGetDevAOVoltageRngs(name)
        for i in range(0, len(raw_limits), 2):
            Vmin, Vmax = raw_limits[i], raw_limits[i + 1]
            AO_ranges.append([Vmin, Vmax])
        # Find range with the largest maximum voltage and use that:
        Vmin, Vmax = max(AO_ranges, key=lambda range: range[1])
        # Confirm that no other range has a voltage lower than Vmin,
        # since if it does, this violates our assumptions and things might not
        # be as simple as having a single range:
        assert min(AO_ranges)[0] >= Vmin
        capabilities[model]["AO_range"] = [Vmin, Vmax]
    else:
        capabilities[model]["AO_range"] = None

    if capabilities[model]['num_AI'] > 0:
        AI_ranges = []
        raw_limits = DAQmxGetDevAIVoltageRngs(name)
        for i in range(0, len(raw_limits), 2):
            Vmin, Vmax = raw_limits[i], raw_limits[i + 1]
            AI_ranges.append([Vmin, Vmax])
        # Restrict to the ranges allowed for non-differential input:
        AI_ranges = supported_AI_ranges_for_non_differential_input(name, AI_ranges)
        # Find range with the largest maximum voltage and use that:
        Vmin, Vmax = max(AI_ranges, key=lambda range: range[1])
        # Confirm that no other range has a voltage lower than Vmin,
        # since if it does, this violates our assumptions and things might not
        # be as simple as having a single range:
        assert min(AI_ranges)[0] >= Vmin
        capabilities[model]["AI_range"] = [Vmin, Vmax]
    else:
        capabilities[model]["AI_range"] = None

    if capabilities[model]["num_AI"] > 0:
        capabilities[model]["AI_start_delay"] = AI_start_delay(name)
    else:
        capabilities[model]["AI_start_delay"] = None


with open(CAPABILITIES_FILE, 'w', newline='\n') as f:
    data = json.dumps(capabilities, sort_keys=True, indent=4)
    f.write(data)

print("added/updated capabilities for %d models" % len(models))
print("Total models with known capabilities: %d" % len(capabilities))
for model in capabilities:
    if model not in models:
        print(model, 'capabilities not updated')
print("run generate_subclasses.py to make labscript devices for these models")
