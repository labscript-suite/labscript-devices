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
    
    MAX_X = 1
    MAX_Y = 1
    MIN_X = -1
    MIN_Y = -1
    def __init__(self, name, parent_device, connection):
        Device.__init__(self, name, parent_device, connection)
        self.xaxis = StaticAnalogQuantity(self.name + '_xaxis', self, 'xaxis', (MIN_X, MAX_X))
        self.yaxis = StaticAnalogQuantity(self.name + '_yaxis', self, 'yaxis', (MIN_Y, MAX_Y))
    
    def set_x(self, value, units=None):
        self.xaxis.constant(value, units)
        
    def set_y(self, value, units=None):
        self.yaxis.constant(value, units)
        

    

@labscript_device
class NewPortMirrorController8742(IntermediateDevice):
    description = 'NewPort Mirror Controller 8742'
    allowed_children = [NewPortControllableMirror]
    
    
