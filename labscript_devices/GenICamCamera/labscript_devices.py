#####################################################################
#                                                                   #
# /labscript_devices/GenICamCamera/labscript_devices.py             #
#                                                                   #
# Copyright 2026, Christopher Billington                            #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from labscript import set_passed_properties

from labscript_devices.common.triggerable_camera.labscript_devices import (
    TriggerableCamera,
)


class GenICamCamera(TriggerableCamera):
    description = 'GenICam camera'

    @set_passed_properties(property_names={"connection_table_properties": ["cti_file"]})
    def __init__(
        self, name, parent_device, connection, serial_number, cti_file=None, **kwargs
    ):
        """A GigE Vision or USB3 Vision camera, controlled through a GenTL producer with
        the harvesters package, and triggered with a digital edge.

        The arguments are those of :obj:`TriggerableCamera
        <labscript_devices.common.triggerable_camera.labscript_devices.TriggerableCamera>`,
        with these differences:

        Args:
            serial_number (str)
                The camera's serial number as the GenTL producer reports it.

            cti_file (str, optional)
                The path of the GenTL producer (a .cti file) on the computer that runs
                the BLACS worker. If not given, every producer in the directories of
                the ``GENICAM_GENTL64_PATH`` environment variable is used.
        """
        super().__init__(name, parent_device, connection, serial_number, **kwargs)

    def _set_serial_number(self, serial_number):
        self.serial_number = str(serial_number)
        self.BLACS_connection = self.serial_number
