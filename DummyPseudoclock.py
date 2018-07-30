#####################################################################
#                                                                   #
# /labscript_devices/DummyPseudoclock.py                            #
#                                                                   #
# Copyright 2017, Joint Quantum Institute                           #
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


from labscript_devices import labscript_device, BLACS_tab, BLACS_worker
from labscript import PseudoclockDevice, Pseudoclock, ClockLine

@labscript_device
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
        group = self.init_device_group(hdf5_file)


from blacs.device_base_class import DeviceTab, define_state, MODE_BUFFERED
from blacs.tab_base_classes import Worker


@BLACS_tab
class DummyPseudoclockTab(DeviceTab):
    def initialise_workers(self):
        worker_initialisation_kwargs = {}
        self.create_worker("main_worker", DummyPseudoclockWorker, worker_initialisation_kwargs)
        self.primary_worker = "main_worker"

    @define_state(MODE_BUFFERED, True)  
    def start_run(self, notify_queue):
        notify_queue.put('done')

@BLACS_worker
class DummyPseudoclockWorker(Worker):
    def program_manual(self, values):
        return {}

    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):
        return {}
    
    def transition_to_manual(self):
        return True

    def shutdown(self):
        return
