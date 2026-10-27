#####################################################################
#                                                                   #
# /labscript_devices/IMAQdxCamera/blacs_workers.py                  #
#                                                                   #
# Copyright 2019, Monash University and contributors                #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

# Original imaqdx_camera server by dt, with modifications by rpanderson and cbillington.

import sys

# MockCamera is imported for camera packages that import it from this module
from labscript_devices.common.triggerable_camera.blacs_workers import (
    CameraInterface,
    MockCamera,
    TriggerableCameraWorker,
)

# Don't import nv yet, so that the worker can run as a mock device, and subclasses can
# import this module to inherit classes, without NI-IMAQdx installed
nv = None


class IMAQdx_Camera(CameraInterface):
    def __init__(self, serial_number):
        super().__init__()
        global nv
        from labscript_devices.IMAQdxCamera import imaqdx as nv

        # Find the camera:
        print("Finding camera...")
        for cam in nv.IMAQdxEnumerateCameras(True):
            if serial_number == (cam.SerialNumberHi << 32) + cam.SerialNumberLo:
                self.camera = cam
                break
        else:
            msg = f"No connected camera with serial number {serial_number:X} found"
            raise Exception(msg)
        # Connect to the camera:
        print("Connecting to camera...")
        self.imaqdx = nv.IMAQdxOpenCamera(
            self.camera.InterfaceName.decode('utf8'),
            nv.IMAQdxCameraControlModeController,
        )
        # Keep an img attribute so we don't have to create it every time
        self.img = nv.imaqCreateImage(nv.IMAQ_IMAGE_U16, 0)

    def set_attribute(self, name, value):
        """Set the value of the attribute of the given name to the given value"""
        try:
            nv.IMAQdxSetAttribute(self.imaqdx, name, value)
        except Exception as e:
            # Add some info to the exception:
            msg = f"failed to set attribute {name} to {value}"
            raise Exception(msg) from e

    def get_attribute_names(self, visibility_level, writeable_only=True):
        """Return a list of all attribute names of readable attributes, for the given
        visibility level. Optionally return only writeable attributes"""
        visibilities = {
            'simple': nv.IMAQdxAttributeVisibilitySimple,
            'intermediate': nv.IMAQdxAttributeVisibilityIntermediate,
            'advanced': nv.IMAQdxAttributeVisibilityAdvanced,
        }
        visibility_level = visibilities[visibility_level.lower()]
        attributes = []
        for a in nv.IMAQdxEnumerateAttributes2(self.imaqdx, '', visibility_level):
            if writeable_only and not a.Writable:
                continue
            if not a.Readable:
                continue
            attributes.append(a.Name.decode('utf8'))
        return attributes

    def get_attribute(self, name):
        """Return current value of attribute of the given name"""
        try:
            return nv.IMAQdxGetAttribute(self.imaqdx, name)
        except Exception as e:
            # Add some info to the exception:
            raise Exception(f"Failed to get attribute {name}") from e

    def snap(self):
        """Acquire a single image and return it"""
        nv.IMAQdxSnap(self.imaqdx, self.img)
        return nv.imaqImageToArray(self.img)

    def configure_acquisition(self, continuous=True, bufferCount=5):
        nv.IMAQdxConfigureAcquisition(self.imaqdx, continuous, bufferCount)
        nv.IMAQdxStartAcquisition(self.imaqdx)

    def grab(self, waitForNextBuffer=True):
        nv.IMAQdxGrab(self.imaqdx, self.img, waitForNextBuffer=waitForNextBuffer)
        return nv.imaqImageToArray(self.img)

    def grab_multiple(self, n_images, images, waitForNextBuffer=True):
        print(f"Attempting to grab {n_images} images.")
        for i in range(n_images):
            while True:
                if self._abort_acquisition:
                    print("Abort during acquisition.")
                    self._abort_acquisition = False
                    return
                try:
                    images.append(self.grab(waitForNextBuffer))
                    print(f"Got image {i+1} of {n_images}.")
                    break
                except nv.IMAQdxError as e:
                    if e.code == nv.IMAQdxErrorTimeout:
                        print('.', end='')
                        continue
                    
                    if self.exception_on_failed_shot:
                        raise
                    else:
                        # stop acquisition
                        print(e, file=sys.stderr)
                        break
                    
                    
                    
        print(f"Got {len(images)} of {n_images} images.")

    def stop_acquisition(self):
        nv.IMAQdxStopAcquisition(self.imaqdx)
        nv.IMAQdxUnconfigureAcquisition(self.imaqdx)

    def close(self):
        nv.IMAQdxCloseCamera(self.imaqdx)
        nv.imaqDispose(self.img)


class IMAQdxCameraWorker(TriggerableCameraWorker):
    interface_class = IMAQdx_Camera
