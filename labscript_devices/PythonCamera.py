#####################################################################
#                                                                   #
# /labscript_devices/PythonCamera.py                                #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from labscript_devices import BLACS_tab
from labscript_devices.Camera import Camera, CameraTab
from labscript import set_passed_properties


class PythonCamera(Camera):
    """A class for new features not compatible with the legacy Camera class"""
    description = 'Python camera'        
    
    @set_passed_properties(
        property_names = {
            "device_properties": ["acquisition_ROI"]}
        )
    def __init__(self, *args, **kwargs):
        self.acquisition_ROI = kwargs.pop('acquisition_ROI', None)
        Camera.__init__(self, *args, **kwargs)
    
    def set_acquisition_ROI(self, acquisition_ROI):
        # acq_ROI is a tuple of form (width, height, offset_X, offset_Y) This
        # method can be used in a script to overwrite a camera's acquisition_ROI
        # after instantiation, so that BlACS does not detect a connection table
        # change on disk when the same file is being imported by experiment scripts
        # and used as the lab connection table.
        self.set_property('acquisition_ROI', acquisition_ROI,
                          location='device_properties', overwrite=True)


@BLACS_tab
class PythonCameraTab(CameraTab):
    pass
