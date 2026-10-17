#####################################################################
#                                                                   #
# /labscript_devices/AD9959DDSSweeper/register_classes.py           #
#                                                                   #
# Copyright 2025, Carter Turnbaugh                                  #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################

from labscript_devices import register_classes

register_classes(
    'AD9959DDSSweeper',
    BLACS_tab='labscript_devices.AD9959DDSSweeper.blacs_tabs.AD9959DDSSweeperTab',
    runviewer_parser='labscript_devices.AD9959DDSSweeper.runviewer_parsers.AD9959DDSSweeperParser',
)
