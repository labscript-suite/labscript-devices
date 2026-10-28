#####################################################################
#                                                                   #
# /labscript_devices/DummyIntermediateDevice/register_classes.py    #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
import labscript_devices

labscript_devices.register_classes(
    'DummyIntermediateDevice',
    BLACS_tab='labscript_devices.DummyIntermediateDevice.blacs_tabs.DummyIntermediateDeviceTab',
    runviewer_parser='labscript_devices.DummyIntermediateDevice.runviewer_parsers.DummyIntermediateDeviceParser',
)
