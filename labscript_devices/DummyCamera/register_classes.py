#####################################################################
#                                                                   #
# /labscript_devices/DummyCamera/register_classes.py                #
#                                                                   #
# Copyright 2026, Ian Spielman and contributors                     #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

from labscript_devices import register_classes

register_classes(
    'DummyCamera',
    BLACS_tab='labscript_devices.DummyCamera.blacs_tabs.DummyCameraTab',
    runviewer_parser=None,
)
