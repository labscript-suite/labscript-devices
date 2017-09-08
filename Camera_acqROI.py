#####################################################################
#                                                                   #
# /labscript_devices/Camera_acqROI.py                                      #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

try:
    from labscript_utils import check_version
except ImportError:
    raise ImportError('Require labscript_utils > 2.1.0')
    
check_version('labscript', '2.0.1', '3')

from labscript_devices import labscript_device, BLACS_tab
from labscript_devices.Camera import Camera, CameraTab
from labscript import set_passed_properties

@labscript_device
class Camera_acqROI(Camera):
    description = 'Generic Camera with acquisition_ROI attribute'        
    
    # To be set as instantiation arguments:
    trigger_edge_type = None
    minimum_recovery_time = None
    
    @set_passed_properties(
        property_names = {
            "device_properties": ["acquisition_ROI"]}
        )
    def __init__(self, acquisition_ROI=None, *args,
                 **kwargs):
                    
        # not a class attribute, so we don't have to have a subclass for each model of camera:
        self.acquisition_ROI = acquisition_ROI
        
        Camera.__init__(self, *args, **kwargs)
    
    def set_acquisition_ROI(self, acq_ROI):
        # acq_ROI is a tuple of form (width, height, offset_X, offset_Y)
        # This method is used in a script to overwrite a camera's
        # acquisition_ROI without throwing errors in the connection table.
        self.set_property('acquisition_ROI', acq_ROI, location='device_properties', overwrite=True)

@BLACS_tab
class Camera_acqROITab(CameraTab):
    pass
