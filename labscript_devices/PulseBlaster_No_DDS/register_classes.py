#####################################################################
#                                                                   #
# /labscript_devices/PulseBlaster_No_DDS/register_classes.py        #
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
    'PulseBlaster_No_DDS',
    BLACS_tab='labscript_devices.PulseBlaster_No_DDS.blacs_tabs.Pulseblaster_No_DDS_Tab',
    runviewer_parser='labscript_devices.PulseBlaster_No_DDS.runviewer_parsers.PulseBlaster_No_DDS_Parser',
)
