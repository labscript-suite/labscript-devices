#####################################################################
#                                                                   #
# /labscript_devices/DummyPseudoclock/register_classes.py           #
#                                                                   #
# Copyright 2017, Christopher Billington                            #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
import labscript_devices

labscript_devices.register_classes(
    'DummyPseudoclock',
    BLACS_tab='labscript_devices.DummyPseudoclock.blacs_tabs.DummyPseudoclockTab',
    runviewer_parser=None, #TODO make a runviwer parser for Dummy pseudoclock!
)
