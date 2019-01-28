#####################################################################
#                                                                   #
# /labscript_devices/DummyPseudoclock/DummyPseudoclock.py           #
#                                                                   #
# Copyright 2017, Christopher Billington                            #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from __future__ import division, unicode_literals, print_function, absolute_import
from labscript_utils import PY2
if PY2:
    str = unicode

# This file represents a dummy labscript device for purposes of testing BLACS
# and labscript. The device is a PseudoclockDevice, and can be the sole device
# in a connection table or experiment.

import labscript_utils.h5_lock
import h5py
from labscript import PseudoclockDevice, Pseudoclock, ClockLine


class DummyPseudoclock(PseudoclockDevice):

    description = 'Dummy pseudoclock'
    clock_limit = 1e6
    clock_resolution = 1e-6

    def __init__(self, name='dummy_pseudoclock', BLACS_connection='dummy_connection', **kwargs):
        self.BLACS_connection = BLACS_connection
        PseudoclockDevice.__init__(self, name, None, None, **kwargs)
        self.pseudoclock = Pseudoclock(self.name + '_pseudoclock', self, 'pseudoclock')
        self.clockline = ClockLine(name='clockline', pseudoclock=self.pseudoclock, connection='dummy')

    def generate_code(self, hdf5_file):
        PseudoclockDevice.generate_code(self, hdf5_file)
        group = self.init_device_group(hdf5_file)
        self.set_property('stop_time', self.stop_time, location='device_properties')