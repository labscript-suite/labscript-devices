#####################################################################
#                                                                   #
# /labscript_devices/PrawnBlaster/register_classes.py               #
#                                                                   #
# Copyright 2021, Philip Starkey                                    #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
import labscript_devices

labscript_device_name = 'PrawnBlaster'
blacs_tab = 'labscript_devices.PrawnBlaster.blacs_tabs.PrawnBlasterTab'
parser = 'labscript_devices.PrawnBlaster.runviewer_parsers.PrawnBlasterParser'

labscript_devices.register_classes(
    labscript_device_name=labscript_device_name,
    BLACS_tab=blacs_tab,
    runviewer_parser=parser,
)
