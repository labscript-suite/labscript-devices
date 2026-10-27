#####################################################################
#                                                                   #
# /labscript_devices/ThorlabsTSICamera/blacs_tabs.py                #
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


class ThorlabsTSICameraTab(TriggerableCameraTab):
    worker_class = (
        'labscript_devices.ThorlabsTSICamera.blacs_workers.ThorlabsTSICameraWorker'
    )
