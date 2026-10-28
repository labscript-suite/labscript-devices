#####################################################################
#                                                                   #
# /labscript_devices/PineBlaster/register_classes.py                #
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
    'PineBlaster',
    BLACS_tab='labscript_devices.PineBlaster.blacs_tabs.PineblasterTab',
    runviewer_parser='labscript_devices.PineBlaster.runviewer_parsers.RunviewerClass',
)
