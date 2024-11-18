#####################################################################
#                                                                   #
# /naqslab_devices/NovaTechDDS/register_classes.py                  #
#                                                                   #
# Copyright 2017, Christopher Billington, David Meyer               #
#                                                                   #
# This file is part of naqslab_devices,                             #
# and is licensed under the                                         #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
import labscript_devices

labscript_devices.register_classes(
    'NovaTech409B',
    BLACS_tab='naqslab_devices.NovaTechDDS.blacs_tab.NovaTech409BTab',
    runviewer_parser='naqslab_devices.NovaTechDDS.runviewer_parser.NovaTech409BParser',
)

labscript_devices.register_classes(
    'NovaTech409B_AC',
    BLACS_tab='naqslab_devices.NovaTechDDS.blacs_tab.NovaTech409B_ACTab',
    runviewer_parser='naqslab_devices.NovaTechDDS.runviewer_parser.NovaTech409B_ACParser',
)

labscript_devices.register_classes(
    'NovaTech440A',
    BLACS_tab='naqslab_devices.NovaTechDDS.blacs_tab.NovaTech440ATab',
    runviewer_parser='naqslab_devices.NovaTechDDS.runviewer_parser.NovaTech440AParser')
