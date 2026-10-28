#####################################################################
#                                                                   #
# /labscript_devices/PulseBlaster_SP2_24_100_32k/register_classes.py #
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
    'PulseBlaster_SP2_24_100_32k',
    BLACS_tab='labscript_devices.PulseBlaster_SP2_24_100_32k.blacs_tabs.PulseBlaster_SP2_24_100_32k_Tab',
    runviewer_parser='labscript_devices.PulseBlaster_SP2_24_100_32k.runviewer_parsers.PulseBlaster_SP2_24_100_32k_Parser',
)
