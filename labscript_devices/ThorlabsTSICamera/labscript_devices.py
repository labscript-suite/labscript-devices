#####################################################################
#                                                                   #
# /labscript_devices/ThorlabsTSICamera/labscript_devices.py         #
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
from labscript_devices.common.triggerable_camera.labscript_devices import TriggerableCamera


class ThorlabsTSICamera(TriggerableCamera):
    description = 'Thorlabs TSI Camera'

    @set_passed_properties(property_names={"device_properties": ["trigger_edge_type"]})
    def __init__(self, name, parent_device, connection, serial_number, **kwargs):
        """A Thorlabs scientific camera (Zelux, Kiralux or Quantalux), controlled with
        the Thorlabs camera SDK and triggered with a digital pulse.

        The arguments are those of :obj:`TriggerableCamera
        <labscript_devices.common.triggerable_camera.labscript_devices.TriggerableCamera>`,
        with these differences:

        Args:
            serial_number (str or int)
                The camera's serial number, which is decimal. A string is not
                interpreted as hexadecimal.

            trigger_edge_type (str), default: `'rising'`
                The edge of the trigger pulse on which an exposure starts. The camera is
                programmed to expect this edge. In bulb mode, the camera exposes while
                the trigger is high for `'rising'`, and while it is low for
                `'falling'`.
        """
        super().__init__(name, parent_device, connection, serial_number, **kwargs)

    def _set_serial_number(self, serial_number):
        self.serial_number = str(serial_number)
        self.BLACS_connection = self.serial_number
