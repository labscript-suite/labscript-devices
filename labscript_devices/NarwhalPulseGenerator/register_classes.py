#####################################################################
#                                                                   #
# /labscript_devices/NarwhalPulseGenerator/register_classes.py      #
#                                                                   #
# Copyright 2026, Christopher Billington                            #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
import labscript_devices

labscript_devices.register_classes(
    labscript_device_name="NarwhalPulseGenerator",
    BLACS_tab="labscript_devices.NarwhalPulseGenerator.blacs_tabs.NarwhalPulseGeneratorTab",
    runviewer_parser="labscript_devices.NarwhalPulseGenerator.runviewer_parsers.NarwhalPulseGeneratorParser",
)
