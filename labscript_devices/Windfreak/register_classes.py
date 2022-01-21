#####################################################################
#                                                                   #
# /labscript_devices/Windfreak/register_classes.py                  #
#                                                                   #
# Copyright 2022, Monash University and contributors                #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

import labscript_devices

labscript_devices.register_classes(
    'WindfreakSynth',
    BLACS_tab='labscript_devices.Windfreak.blacs_tabs.WindfreakSynthTab',
    runviewer_parser=None
)