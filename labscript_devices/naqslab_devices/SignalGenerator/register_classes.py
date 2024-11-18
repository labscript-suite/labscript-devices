#####################################################################
#                                                                   #
# /naqslab_devices/SignalGenerator/register_classes.py              #
#                                                                   #
# Copyright 2018, David Meyer                                       #
#                                                                   #
# This file is part of naqslab_devices,                             #
# and is licensed under the                                         #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
"""Configures which BLACS_tab goes to which labscript_device."""

import labscript_devices

labscript_devices.register_classes(
    'RS_SMF100A',
    BLACS_tab='naqslab_devices.SignalGenerator.BLACS.RS_SMF100A.RS_SMF100ATab',
    runviewer_parser='')
    
labscript_devices.register_classes(
    'RS_SMA100B',
    BLACS_tab='naqslab_devices.SignalGenerator.BLACS.RS_SMA100B.RS_SMA100BTab',
    runviewer_parser='')

labscript_devices.register_classes(
    'RS_SMHU',
    BLACS_tab='naqslab_devices.SignalGenerator.BLACS.RS_SMHU.RS_SMHUTab',
    runviewer_parser='')
    
labscript_devices.register_classes(
    'HP_8643A',
    BLACS_tab='naqslab_devices.SignalGenerator.BLACS.HP_8643A.HP_8643ATab',
    runviewer_parser='')
    
labscript_devices.register_classes(
    'HP_8642A',
    BLACS_tab='naqslab_devices.SignalGenerator.BLACS.HP_8642A.HP_8642ATab',
    runviewer_parser='')

labscript_devices.register_classes(
    'HP_8648A',
    BLACS_tab='naqslab_devices.SignalGenerator.BLACS.HP_8648.HP_8648ATab',
    runviewer_parser='')
    
labscript_devices.register_classes(
    'HP_8648B',
    BLACS_tab='naqslab_devices.SignalGenerator.BLACS.HP_8648.HP_8648BTab',
    runviewer_parser='')
    
labscript_devices.register_classes(
    'HP_8648C',
    BLACS_tab='naqslab_devices.SignalGenerator.BLACS.HP_8648.HP_8648CTab',
    runviewer_parser='')
    
labscript_devices.register_classes(
    'HP_8648D',
    BLACS_tab='naqslab_devices.SignalGenerator.BLACS.HP_8648.HP_8648DTab',
    runviewer_parser='')
    
labscript_devices.register_classes(
    'E8257N',
    BLACS_tab='naqslab_devices.SignalGenerator.BLACS.KeysightSigGens.E8257NTab',
    runviewer_parser='')
