#####################################################################
#                                                                   #
# /labscript_devices/DummyIntermediateDevice/blacs_tabs.py          #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from blacs.device_base_class import DeviceTab


class DummyIntermediateDeviceTab(DeviceTab):
    def initialise_GUI(self):
        self.create_worker("main_worker","labscript_devices.DummyIntermediateDevice.blacs_workers.DummyIntermediateDeviceWorker",{})
        self.primary_worker = "main_worker"
