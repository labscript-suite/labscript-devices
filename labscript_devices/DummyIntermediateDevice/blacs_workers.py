#####################################################################
#                                                                   #
# /labscript_devices/DummyIntermediateDevice/blacs_workers.py       #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from blacs.tab_base_classes import Worker


class DummyIntermediateDeviceWorker(Worker):
    def init(self):
        pass

    def program_manual(self, front_panel_values):
        return front_panel_values 

    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):
        return initial_values

    def transition_to_manual(self,abort = False):
        return True

    def abort_transition_to_buffered(self):
        return self.transition_to_manual(True)
        
    def abort_buffered(self):
        return self.transition_to_manual(True)

    def shutdown(self):
        pass
