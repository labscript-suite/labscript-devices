#####################################################################
#                                                                   #
# /DummyIntermediateDevice.py                                       #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################


# This file represents a dummy labscript device for purposes of testing BLACS
# and labscript. The device is a Intermediate Device, and can be attached to
# a pseudoclock in labscript in order to test the pseudoclock behaviour
# without needing a real Intermediate Device. 
# 
# You can attach an arbitrary number of outputs to this device, however we
# currently only support outputs of type AnalogOut and DigitalOut. I would be
# easy to extend this is anyone needed further functionality.


from labscript_devices import labscript_device, BLACS_tab, BLACS_worker
from labscript import IntermediateDevice, DigitalOut, AnalogOut, config
import numpy as np

class DummyIntermediateDevice(IntermediateDevice):

    description = 'Dummy IntermediateDevice'
    clock_limit = 1e6

    # If this is updated, then you need to update generate_code to support whatever types you add
    allowed_children = [DigitalOut, AnalogOut]

    def __init__(self, name, parent_device, BLACS_connection='dummy_connection', **kwargs):
        self.BLACS_connection = BLACS_connection
        IntermediateDevice.__init__(self, name, parent_device, **kwargs)

    def generate_code(self, hdf5_file):
        IntermediateDevice.generate_code(self, hdf5_file)
        group = self.init_device_group(hdf5_file)

        clockline = self.parent_device
        pseudoclock = clockline.parent_device
        times = pseudoclock.times[clockline]

        # out_table = np.empty((len(times),len(self.child_devices)), dtype=np.float32)
        # determine dtypes
        dtypes = []
        for device in self.child_devices:
            if isinstance(device, DigitalOut):
                device_dtype = np.int8
            elif isinstance(device, AnalogOut):
                device_dtype = np.float64
            dtypes.append((device.name, device_dtype))

        # create dataset
        out_table = np.zeros(len(times), dtype=dtypes)
        for device in self.child_devices:
            out_table[device.name][:] = device.raw_output

        group.create_dataset('OUTPUTS', compression=config.compression, data=out_table)


from blacs.device_base_class import DeviceTab
from blacs.tab_base_classes import Worker

@BLACS_tab
class DummyIntermediateDeviceTab(DeviceTab):
    def initialise_GUI(self):
        self.create_worker("main_worker",DummyIntermediateDeviceWorker,{})
        self.primary_worker = "main_worker"

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