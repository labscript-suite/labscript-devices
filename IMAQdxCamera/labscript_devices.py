#####################################################################
#                                                                   #
# /labscript_devices/IMAQdxCamera/labscript_devices.py              #
#                                                                   #
# Copyright 2019, Monash University and contributors                #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

from __future__ import division, unicode_literals, print_function, absolute_import

from labscript_utils import check_version
from labscript_utils import PY2
if PY2:
    str = unicode

from labscript_utils import dedent

from labscript_devices import BLACS_tab
from labscript import TriggerableDevice, LabscriptError, set_passed_properties
import numpy as np


class IMAQdxCamera(TriggerableDevice):
    description = 'IMAQdx Camera'

    @set_passed_properties(
        property_names={
            "connection_table_properties": ["serial_number", "orientation"],
            "device_properties": [
                "trigger_edge_type",
                "trigger_duration",
                "minimum_recovery_time",
                "imaqdx_attributes",
            ],
        }
    )
    def __init__(
        self,
        name,
        parent_device,
        connection,
        serial_number=0x0,
        trigger_duration=None,
        orientation='side',
        trigger_edge_type='rising',
        minimum_recovery_time=0,
        imaqdx_attributes=None,
        **kwargs
    ):
        self.trigger_edge_type = trigger_edge_type
        self.minimum_recovery_time = minimum_recovery_time
        self.trigger_duration = trigger_duration
        self.orientation = orientation
        if isinstance(serial_number, (str, bytes)):
            serial_number = int(serial_number, 16)
        self.serial_number = serial_number
        self.BLACS_connection = str(self.serial_number)[2:]
        if imaqdx_attributes is None:
            imaqdx_attributes = {}
        self.exposures = []
        TriggerableDevice.__init__(self, name, parent_device, connection, **kwargs)

    def expose(self, t, name, frametype='', trigger_duration=None):
        if trigger_duration is None:
            trigger_duration = self.trigger_duration
        if trigger_duration is None:
            msg = """%s %s has not had an trigger_duration set as an instantiation
                argument, and none was specified for this exposure"""
            raise ValueError(dedend(msg) % (self.description, self.name))
        if not trigger_duration > 0:
            msg = "trigger_duration must be > 0, not %s" % str(trigger_duration)
            raise ValueError(msg)
        self.trigger(t, trigger_duration)
        self.exposures.append((t, name, frametype, trigger_duration))
        return trigger_duration

    def generate_code(self, hdf5_file):
        self.do_checks()
        table_dtypes = [
            ('time', float),
            ('name', 'a256'),
            ('frametype', 'a256'),
            ('trigger_duration', float),
        ]
        data = np.array(self.exposures, dtype=table_dtypes)
        group = self.init_device_group(hdf5_file)
        if self.exposures:
            group.create_dataset('EXPOSURES', data=data)
