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
# Refactored as a BLACS worker by cbillington

import sys
from types import MethodType

import numpy as np

from labscript_utils import dedent
from labscript_devices.TriggerableCamera.blacs_workers import (
    TriggerableCameraInterface,
    TriggerableCameraWorker,
)

# Don't import nv yet so as not to throw an error: subclasses import this module to
# inherit its classes, and doing so must not require nivision
nv = None


def _monkeypatch_imaqdispose():
    """Monkeypatch a fix to a memory leak bug in pynivision. The pynivision project is
    no longer active, so we can't contribute this fix upstream. In the long run,
    hopefully someone (perhaps us) forks it so that bugs can be addressed in the
    normal way"""

    import nivision.core
    import ctypes

    _imaqDispose = nivision.core._imaqDispose

    def imaqDispose(obj):
        if getattr(obj, "_contents", None) is not None:
            _imaqDispose(ctypes.byref(obj._contents))
            obj._contents = None
        if getattr(obj, "value", None) is not None:
            _imaqDispose(obj)
            obj.value = None
        # This is the bugfix: pointers as raw ints were not being disposed:
        if isinstance(obj, int):
            _imaqDispose(obj)

    nivision.core.imaqDispose = nv.imaqDispose = imaqDispose


class IMAQdx_Camera(TriggerableCameraInterface):
    def __init__(self, serial_number):
        global nv
        import nivision as nv
        _monkeypatch_imaqdispose()

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
            self.camera.InterfaceName, nv.IMAQdxCameraControlModeController
        )
        # Keep an img attribute so we don't have to create it every time
        self.img = nv.imaqCreateImage(nv.IMAQ_IMAGE_U16)

    def set_attributes(self, attr_dict):
        for k, v in attr_dict.items():
            self.set_attribute(k, v)

    def set_attribute(self, name, value):
        """Set the value of the attribute of the given name to the given value"""
        _value = value  # Keep the original for the sake of the error message
        if isinstance(_value, str):
            _value = _value.encode('utf8')
        try:
            nv.IMAQdxSetAttribute(self.imaqdx, name.encode('utf8'), _value)
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
        for a in nv.IMAQdxEnumerateAttributes2(self.imaqdx, b'', visibility_level):
            if writeable_only and not a.Writable:
                continue
            if not a.Readable:
                continue
            attributes.append(a.Name.decode('utf8'))
        return attributes

    def get_attribute(self, name):
        """Return current value of attribute of the given name"""
        try:
            value = nv.IMAQdxGetAttribute(self.imaqdx, name.encode('utf8'))
            if isinstance(value, nv.core.IMAQdxEnumItem):
                value = value.Name
            if isinstance(value, bytes):
                value = value.decode('utf8')
            return value
        except Exception as e:
            # Add some info to the exception:
            raise Exception(f"Failed to get attribute {name}") from e

    def snap(self):
        """Acquire a single image and return it"""
        nv.IMAQdxSnap(self.imaqdx, self.img)
        return self._decode_image_data(self.img)

    def configure_acquisition(self, continuous=True, bufferCount=5):
        nv.IMAQdxConfigureAcquisition(
            self.imaqdx, continuous=continuous, bufferCount=bufferCount
        )
        nv.IMAQdxStartAcquisition(self.imaqdx)

    def grab(self, waitForNextBuffer=True):
        nv.IMAQdxGrab(self.imaqdx, self.img, waitForNextBuffer=waitForNextBuffer)
        return self._decode_image_data(self.img)

    def is_transient_grab_error(self, exception):
        """IMAQdx reports a frame that has not arrived yet as a timeout."""
        return (
            isinstance(exception, nv.ImaqDxError)
            and exception.code == nv.IMAQdxErrorTimeout.value
        )

    def is_skippable_grab_error(self, exception):
        """Anything else IMAQdx itself reports, as against a fault above it."""
        return isinstance(exception, nv.ImaqDxError)

    def stop_acquisition(self):
        nv.IMAQdxStopAcquisition(self.imaqdx)
        nv.IMAQdxUnconfigureAcquisition(self.imaqdx)

    def _decode_image_data(self, img):
        img_array = nv.imaqImageToArray(img)
        img_array_shape = (img_array[2], img_array[1])
        # bitdepth in bytes
        bitdepth = len(img_array[0]) // (img_array[1] * img_array[2])
        dtype = {1: np.uint8, 2: np.uint16, 4: np.uint32}[bitdepth]
        data = np.frombuffer(img_array[0], dtype=dtype).reshape(img_array_shape)
        return data.copy()

    def close(self):
        nv.IMAQdxCloseCamera(self.imaqdx)


class IMAQdxCameraWorker(TriggerableCameraWorker):
    """Worker for :obj:`IMAQdx_Camera`.

    A subclass of this may name a camera that does not subclass
    :obj:`TriggerableCameraInterface`, and the camera's attributes are then read
    one at a time. That route is deprecated, and says so when the worker starts.
    """

    interface_class = IMAQdx_Camera

    def init(self):
        super().init()
        # Here rather than in get_camera, which a lab's own worker may override.
        if not hasattr(self.camera, 'get_attributes_as_dict'):
            msg = f"""Warning: {type(self.camera).__name__} does not subclass
                TriggerableCameraInterface. Driving such a camera by subclassing
                IMAQdxCameraWorker is deprecated. Use the TriggerableCamera
                device, with a camera class that subclasses
                TriggerableCameraInterface and a worker that subclasses
                TriggerableCameraWorker."""
            print(dedent(msg), file=sys.stderr)
            self.camera.get_attributes_as_dict = MethodType(
                TriggerableCameraInterface.get_attributes_as_dict, self.camera
            )
