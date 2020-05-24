#####################################################################
#                                                                   #
# /NI_DAQmx/register_classes.py                                     #
#                                                                   #
# Copyright 2018, Monash University, JQI, Christopher Billington    #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################
import os
import json
from labscript_devices import register_classes

THIS_FOLDER = os.path.dirname(os.path.abspath(__file__))
CAPABILITIES_FILE = os.path.join(THIS_FOLDER, 'models', 'capabilities.json')

capabilities = {}
if os.path.exists(CAPABILITIES_FILE):
    with open(CAPABILITIES_FILE) as f:
        capabilities = json.load(f)

# The base class:
register_classes(
    'NI_DAQmx',
    BLACS_tab='labscript_devices.NI_DAQmx.blacs_tabs.NI_DAQmxTab',
    runviewer_parser='labscript_devices.NI_DAQmx.runviewer_parsers.NI_DAQmxParser',
)

# All the auto-generated subclasses:
for model_name in capabilities:
    class_name = 'NI_' + model_name.replace('-', '_')
    register_classes(
        class_name,
        BLACS_tab='labscript_devices.NI_DAQmx.blacs_tabs.NI_DAQmxTab',
        runviewer_parser='labscript_devices.NI_DAQmx.runviewer_parsers.NI_DAQmxParser',
    )
