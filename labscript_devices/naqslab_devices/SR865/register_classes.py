#####################################################################
#                                                                   #
# /naqslab_devices/SR865/register_classes.py                        #
#                                                                   #
# Copyright 2018, David Meyer                                       #
#                                                                   #
# This file is part of naqslab_devices,                             #
# and is licensed under the                                         #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
import labscript_devices

labscript_devices.register_classes(
    'SR865',
    BLACS_tab='naqslab_devices.SR865.blacs_tab.SR865Tab',
    runviewer_parser='')
