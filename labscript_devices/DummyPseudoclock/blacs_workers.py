#####################################################################
#                                                                   #
# /labscript_devices/DummyPseudoclock/blacs_worker.py               #
#                                                                   #
# Copyright 2017, Christopher Billington                            #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
import time
import labscript_utils.h5_lock
import h5py
from blacs.tab_base_classes import Worker
import labscript_utils.properties as properties

class DummyPseudoclockWorker(Worker):
    def program_manual(self, values):
        return {}

    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):
        # get stop time:
        with h5py.File(h5file, 'r') as f:
            props = properties.get(f, self.device_name, 'device_properties')
            self.stop_time = props.get('stop_time', None) # stop_time may be absent if we are not the master pseudoclock
        return {}
    
    def check_if_done(self):
        # Wait up to 1 second for the shot to be done, returning True if it is
        # or False if not.
        if getattr(self, 'start_time', None) is None:
            self.start_time = time.time()
        timeout = min(self.start_time + self.stop_time - time.time(), 1)
        if timeout < 0:
            return True
        time.sleep(timeout)
        return self.start_time + self.stop_time < time.time()

    def transition_to_manual(self):
        self.start_time = None
        self.stop_time = None
        return True

    def shutdown(self):
        return

    def abort_buffered(self):
        return self.transition_to_manual()
