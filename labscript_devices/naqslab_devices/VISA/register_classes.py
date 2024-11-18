#####################################################################
#                                                                   #
# /naqslab_devices/VISA/register_classes.py                         #
#                                                                   #
# Copyright 2018, David Meyer                                       #
#                                                                   #
# This file is part of naqslab_devices,                             #
# and is licensed under the                                         #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
"""
Sets which BLACS_tab belongs to each labscript device.
"""

import labscript_devices

labscript_devices.register_classes(
    'VISA',
    BLACS_tab='naqslab_devices.VISA.blacs_tab.VISATab',
    runviewer_parser=''
)
