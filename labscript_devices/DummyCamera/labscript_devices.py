#####################################################################
#                                                                   #
# /labscript_devices/DummyCamera/labscript_devices.py               #
#                                                                   #
# Copyright 2026, Ian Spielman and contributors                     #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
import numpy as np
from labscript import LabscriptError

from labscript_devices.common.triggerable_camera.labscript_devices import (
    TriggerableCamera,
)

# Bits per pixel of the pixel formats that set the saturation level
BIT_DEPTHS = {'Mono8': 8, 'Mono10': 10, 'Mono12': 12, 'Mono14': 14, 'Mono16': 16}


def image_size(camera_attributes):
    """Return the (width, height) of a dummy camera's images from its attributes"""
    missing = [key for key in ('Width', 'Height') if key not in camera_attributes]
    if missing:
        msg = "A DummyCamera requires 'Width' and 'Height' in camera_attributes"
        raise LabscriptError(msg)
    return int(camera_attributes['Width']), int(camera_attributes['Height'])


class DummyCamera(TriggerableCamera):
    """A camera without hardware, the images of which are computed when the shot is
    compiled.

    The arguments are those of :obj:`TriggerableCamera
    <labscript_devices.common.triggerable_camera.labscript_devices.TriggerableCamera>`,
    and `serial_number` is optional. `camera_attributes` must contain `'Width'` and
    `'Height'`, the size of the images in pixels, and may contain `'PixelFormat'`, one
    of `'Mono8'`, `'Mono10'`, `'Mono12'`, `'Mono14'` and `'Mono16'` (the default), which
    sets the saturation level.
    """

    description = 'Dummy camera'

    def __init__(self, name, parent_device, connection, serial_number=0, **kwargs):
        super().__init__(name, parent_device, connection, serial_number, **kwargs)
        image_size(self.camera_attributes)
        pixel_format = self.camera_attributes.get('PixelFormat', 'Mono16')
        if pixel_format not in BIT_DEPTHS:
            msg = f"PixelFormat must be one of {list(BIT_DEPTHS)}, not {pixel_format!r}"
            raise LabscriptError(msg)
        self.image_functions = []

    def expose(
        self, t, name, frametype='frame', trigger_duration=None, function=None, **kwargs
    ):
        """Request an exposure, as for :obj:`TriggerableCamera.expose`. The image is
        `function(X, Y, **kwargs)`, where `X` and `Y` are 2D arrays of the coordinates
        of the pixels in the object plane, in micrometres from the centre of the image:
        the pixel coordinates scaled by `pixel_size` and divided by `magnification`. The
        function returns an array of the same shape, which is clipped to the range of
        the pixel format and rounded down to integers. The function is called during
        compilation, so it can use the globals of the shot. Without a function, the
        image is zero."""
        trigger_duration = super().expose(t, name, frametype, trigger_duration)
        self.image_functions.append((function, kwargs))
        return trigger_duration

    def coordinates(self):
        """Return the X and Y coordinates of the pixels in the object plane, in
        micrometres from the centre of the image"""
        width, height = image_size(self.camera_attributes)
        pixel_x, pixel_y = self.pixel_size
        x = (np.arange(width) - (width - 1) / 2) * pixel_x / self.magnification
        y = (np.arange(height) - (height - 1) / 2) * pixel_y / self.magnification
        return np.meshgrid(x, y)

    def generate_code(self, hdf5_file):
        super().generate_code(hdf5_file)
        if not self.exposures:
            return
        X, Y = self.coordinates()
        bit_depth = BIT_DEPTHS[self.camera_attributes.get('PixelFormat', 'Mono16')]
        images = []
        # The worker matches the images to the exposures sorted by the fields of the
        # EXPOSURES table in order, which is how the exposure tuples sort:
        for i in sorted(range(len(self.exposures)), key=self.exposures.__getitem__):
            function, kwargs = self.image_functions[i]
            if function is None:
                images.append(np.zeros(X.shape, dtype=np.uint16))
                continue
            image = np.asarray(function(X, Y, **kwargs), dtype=float)
            t, name, frametype, _ = self.exposures[i]
            exposure = f"{self.name} exposure {name}/{frametype} at t={t}"
            if image.shape != X.shape:
                msg = f"{exposure}: image has shape {image.shape}, not {X.shape}"
                raise LabscriptError(msg)
            if not np.isfinite(image).all():
                raise LabscriptError(f"{exposure}: image has non-finite values")
            image = np.clip(image, 0, 2**bit_depth - 1)
            images.append(image.astype(np.uint16))
        group = hdf5_file['devices'][self.name]
        group.create_dataset('IMAGES', data=np.array(images), compression='gzip')
