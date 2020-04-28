#####################################################################
#                                                                   #
# /labscript_devices/ZaberStageController/labscript_devices.py      #
#                                                                   #
# Copyright 2019, Monash University and contributors                #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from labscript import StaticAnalogQuantity, IntermediateDevice, set_passed_properties
import numpy as np

from .utils import get_device_number

# Base class for stages:
class ZaberStage(StaticAnalogQuantity):
    limits = (0, np.inf)
    description = "Zaber Stage"
    @set_passed_properties(
        property_names={"connection_table_properties": ["limits"]}
    )
    def __init__(self, *args, limits=None, **kwargs):
        """Static Analog output device for controlling the position of a Zaber stage.
        Can be added as a child device of `ZaberStageController`. Subclasses for
        specific models already have model-specific limits set for their values, but you
        may further restrict these by setting the keyword argument limits=

        Args:
            *args:
                Arguments to be passed to the  `__init__` method of the parent class
                (StaticAnalogQuantity).

            limits (tuple), default `None`
                a two-tuple (min, max) for the minimum and maximum allowed positions, in
                steps, that the device may be instructed to move to via a labscript
                experiment or the BLACS front panel. If None, the limits set as a class
                attribute will be used, which are set to the maximal positions allowed
                by the device if using one of the model-specific subclasses defined in
                this module, or is (0, inf) otherwise.

            **kwargs:
                Further keyword arguments to be passed to the `__init__` method of the
                parent class (StaticAnalogQuantity).

        """

        if limits is None:
            limits = self.limits
        StaticAnalogQuantity.__init__(self, *args, limits=limits, **kwargs)


# Child classes for specific models of stages, which have knowledge of their valid
# ranges:
class ZaberStageTLSR150D(ZaberStage):
    limits = (0, 76346)
    description = 'Zaber Stage T-LSR150D'

class ZaberStageTLSR300D(ZaberStage):
    limits = (0, 151937)
    description = 'Zaber Stage T-LSR300D'

class ZaberStageTLS28M(ZaberStage):
    limits = (0, 282879)
    description = 'Zaber Stage T-LS28-M'

class ZaberStageTLSR300B(ZaberStage):
    limits = (0, 607740)
    description = 'Zaber Stage T-LSR150D'

class ZaberStageController(IntermediateDevice):
    allowed_children = [ZaberStage]

    @set_passed_properties(
        property_names={"connection_table_properties": ["com_port", "mock"]}
    )
    def __init__(self, name, com_port="COM1", mock=False, **kwargs):
        """Device for controlling a number of Zaber stages connected to a serial port.
        Add stages as child devices, either by using one of them model-specific classes
        in this module, or the generic `ZaberStage` class.

        Args:
            name (str)
                device name

            com_port (str), default: `'COM1'`
                Serial port for communication, i.e. `'COM1' etc on Windows or
                `'/dev/USBtty0'` or similar on unix.

            mock (bool, optional), default: False
                For testing purpses, simulate a device instead of communicating with
                actual hardware.

            **kwargs: Further keyword arguments to be passed to the `__init__` method of
                the parent class (IntermediateDevice).

        """

        IntermediateDevice.__init__(self, name, None, **kwargs)
        self.BLACS_connection = com_port

    def add_device(self, device):
        # Error-check the connection string:
        _ = get_device_number(device.connection)
        IntermediateDevice.add_device(self, device)

    def generate_code(self, hdf5_file):
        IntermediateDevice.generate_code(self, hdf5_file)
        stages = {stage.connection: stage for stage in self.child_devices}
        connections = sorted(stages, key=get_device_number)
        dtypes = [(connection, int) for connection in connections]
        static_value_table = np.empty(1, dtype=dtypes)
        for connection, stage in stages.items():
            static_value_table[connection][0] = stage.static_value
        grp = self.init_device_group(hdf5_file)
        grp.create_dataset('static_values', data=static_value_table)
