#####################################################################
#                                                                   #
# /labscript_devices/IMAQdxCamera/blacs_tabs.py                     #
#                                                                   #
# Copyright 2019, Monash University and contributors                #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

from labscript_devices.TriggerableCamera.blacs_tabs import TriggerableCameraTab


class IMAQdxCameraTab(TriggerableCameraTab):
    """Thin sub-class of :obj:`TriggerableCameraTab`.

    This sub-class only defines :obj:`worker_class` to point to the correct
    :obj:`IMAQdxCameraWorker`."""

    # override worker class
    worker_class = 'labscript_devices.IMAQdxCamera.blacs_workers.IMAQdxCameraWorker'
