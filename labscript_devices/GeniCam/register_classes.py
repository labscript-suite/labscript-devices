#####################################################################
#                                                                   #
# /labscript_devices/IMAQdxCamera/register_classes.py               #
#                                                                   #
# Copyright 2019, Monash University and contributors                #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from labscript_devices import register_classes

register_classes(
    'GeniCam',
    BLACS_tab='labscript_devices.GeniCam.blacs_tabs.GeniCamTab',
    runviewer_parser=None,
)
