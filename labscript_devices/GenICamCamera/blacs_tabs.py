#####################################################################
#                                                                   #
# /labscript_devices/GenICamCamera/blacs_tabs.py                    #
#                                                                   #
# Copyright 2026, Christopher Billington                            #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from labscript_devices.common.triggerable_camera.blacs_tabs import TriggerableCameraTab


class GenICamCameraTab(TriggerableCameraTab):
    worker_class = 'labscript_devices.GenICamCamera.blacs_workers.GenICamCameraWorker'

    def get_worker_kwargs(self):
        kwargs = super().get_worker_kwargs()
        table = self.settings['connection_table']
        properties = table.find_by_name(self.device_name).properties
        kwargs['cti_file'] = properties['cti_file']
        return kwargs
