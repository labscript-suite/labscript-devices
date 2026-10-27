#####################################################################
#                                                                   #
# /labscript_devices/ThorlabsTSICamera/register_classes.py          #
#                                                                   #
# Copyright 2026, Christopher Billington                            #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from labscript_devices import register_classes

register_classes(
    'ThorlabsTSICamera',
    BLACS_tab='labscript_devices.ThorlabsTSICamera.blacs_tabs.ThorlabsTSICameraTab',
    runviewer_parser=None,
)
