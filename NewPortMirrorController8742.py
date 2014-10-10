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
    
    MAX_X = 1
    MAX_Y = 1
    MIN_X = -1
    MIN_Y = -1
    default_value = 0.0
    
    def __init__(self, name, parent_device, connection):
        Device.__init__(self, name, parent_device, connection)
        self.xaxis = StaticAnalogQuantity(self.name + '_xaxis', self, 'xaxis', (self.MIN_X, self.MAX_X))
        self.yaxis = StaticAnalogQuantity(self.name + '_yaxis', self, 'yaxis', (self.MIN_Y, self.MAX_Y))
    
    def set_x(self, value, units=None):
        self.xaxis.constant(value, units)
        
    def set_y(self, value, units=None):
        self.yaxis.constant(value, units)
        

@labscript_device
class NewPortMirrorController8742(Device):
    description = 'NewPort Mirror Controller 8742'
    allowed_children = [NewPortControllableMirror]
    
    def __init__(self, name, com_port):
        Device.__init__(self, name, parent_device=None, connection=None)
        self.BLACS_connection = com_port
        
    def add_device(self, device):
        Device.add_device(self, device)
        if device.connection not in ['mirror 0', 'mirror 1']:
            raise LabscriptError('Connection must be either "mirror 0" or "mirror 1"')
        other_devices = [d for d in self.child_devices if d is not device]
        for other_device in other_devices:
            if other_device.connection == device.connection:
                raise LabscriptError('Has same connection as %s' % other_device.name)
     
    def generate_code(self, hdf5_file):
        Device.generate_code(self, hdf5_file)
        dtypes = [('motor %d' %n, float) for n in range(1, 5)]
        out_table = np.zeros(1, dtype=dtypes)
        out_table.fill(float('nan'))
        for mirror in self.child_devices:
            mirror_number = int(mirror.connection.split()[1])
            x_value = mirror.xaxis.static_value
            y_value = mirror.yaxis.static_value
            x_motor_number = 2*mirror_number + 1
            y_motor_number = 2*mirror_number + 2
            out_table[0]['motor %d'%x_motor_number] = x_value   
            out_table[0]['motor %d'%y_motor_number] = y_value  
    
        grp = hdf5_file.create_group('/devices/'+self.name)
        grp.create_dataset('MOTOR_VALUE', compression=config.compression, data=out_table) 
