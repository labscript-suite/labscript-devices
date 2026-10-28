#####################################################################
#                                                                   #
# /labscript_devices/PulseBlaster/register_classes.py               #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################
import labscript_devices

labscript_devices.register_classes(
    'PulseBlaster',
    BLACS_tab='labscript_devices.PulseBlaster.blacs_tabs.PulseBlasterTab',
    runviewer_parser='labscript_devices.PulseBlaster.runviewer_parsers.PulseBlasterParser',
)
