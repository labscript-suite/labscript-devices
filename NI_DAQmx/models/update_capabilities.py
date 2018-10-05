#####################################################################
#                                                                   #
# /NI_DAQmx/models/update_capabilities.py                           #
#                                                                   #
# Copyright 2018, Christopher Billington                            #
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


def port_supports_buffered(device_name, port):
    if 'PFI0' not in DAQmxGetDevTerminals(device_name):
        return False
    npts = 10
    task = Task()
    clock_terminal = '/' + device_name + '/PFI0'
    data = np.zeros(npts, dtype=np.uint8)
    task.CreateDOChan(
        device_name + "/" + port + '/line0', "", c.DAQmx_Val_ChanForAllLines
    )
    task.CfgSampClkTiming(
        clock_terminal, 100, c.DAQmx_Val_Rising, c.DAQmx_Val_FiniteSamps, npts
    )
    written = int32()
    try:
        task.WriteDigitalLines(
            npts, False, 10.0, c.DAQmx_Val_GroupByScanNumber, data, byref(written), None
        )
    except PyDAQmx.DAQmxFunctions.BufferedOperationsNotSupportedOnSelectedLinesError:
        return False
    else:
        return True
    finally:
        task.ClearTask()


capabilities = {}
if os.path.exists(CAPABILITIES_FILE):
    with open(CAPABILITIES_FILE) as f:
        capabilities = json.load(f)


new_devices = []
for name in DAQmxGetSysDevNames().split(', '):
    model = DAQmxGetDevProductType(name)
    print("found device:", name, model)
    if name not in capabilities:
        new_devices.append(model)
    capabilities[model] = {}
    capabilities[model]["supports_buffered_AO"] = DAQmxGetDevAOSampClkSupported(name)
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
        port_info = {}
        capabilities[model]["ports"][port] = port_info
        port_chans = [chan for chan in chans if chan.split('/')[0] == port]
        port_info['num_lines'] = len(port_chans)
        if capabilities[model]["supports_buffered_DO"]:
            port_info['supports_buffered'] = port_supports_buffered(name, port)
        else:
            port_info['supports_buffered'] = False
    capabilities[model]["num_CI"] = len(DAQmxGetDevCIPhysicalChans(name))

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
        # Find range with the largest maximum voltage and use that:
        Vmin, Vmax = max(AI_ranges, key=lambda range: range[1])
        # Confirm that no other range has a voltage lower than Vmin,
        # since if it does, this violates our assumptions and things might not
        # be as simple as having a single range:
        assert min(AI_ranges)[0] >= Vmin
        capabilities[model]["AI_range"] = [Vmin, Vmax]
    else:
        capabilities[model]["AI_range"] = None


with open(CAPABILITIES_FILE, 'w', newline='\n') as f:
    json.dump(capabilities, f, sort_keys=True, indent=4, separators=(',', ': '))

print("added capabilities for %d models" % len(new_devices))
print("run generate_subclasses.py to make labscript devices for these models")
