#####################################################################
#                                                                   #
# /NewPortMirrorController8742.py                                   #
#                                                                   #
# Copyright 2014, Joint Quantum Institute                           #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################

from __future__ import print_function

from labscript_devices import runviewer_parser, labscript_device, BLACS_tab, BLACS_worker

from labscript import IntermediateDevice, Device, config, LabscriptError, StaticAnalogQuantity

import numpy as np
import labscript_utils.h5_lock, h5py

class NewPortControllableMirror(Device):
    description = 'NewPort Mirror'
    allowed_children = [StaticAnalogQuantity]
    generation = 2
    def __init__(self, name, parent_device, connection):
        pass

@labscript_device
class NewPortMirrorController8742(IntermediateDevice):
    description = 'NewPort Mirror Controller 8742'
    allowed_children = [NewPortControllableMirror]
    
    
