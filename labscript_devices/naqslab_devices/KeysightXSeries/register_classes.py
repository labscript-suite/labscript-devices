#####################################################################
#                                                                   #
# /naqslab_devices/KeysightXSeries/register_classes.py              #
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
    'KeysightXScope',
    BLACS_tab='naqslab_devices.KeysightXSeries.blacs_tab.KeysightXScopeTab',
    runviewer_parser='')
