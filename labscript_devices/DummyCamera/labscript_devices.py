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

import re

import numpy as np
from labscript_utils import dedent

from labscript_devices.DummyCamera.sensor import (
    IMAGE_DTYPE,
    blank_image,
    sensor_size,
)
from labscript_devices.TriggerableCamera.labscript_devices import TriggerableCamera


# What a pixel holds when PixelFormat does not say, and the most the shot file can
# store in the uint16 datasets a camera's images are saved as.
DEFAULT_BIT_DEPTH = 16


class DummyCamera(TriggerableCamera):
    """A camera with no hardware, whose images are computed as the shot compiles.

    Each exposure names a function of the camera's coordinate grid. The function
    is evaluated during compilation, where the shot's globals are in scope, and
    the images it returns are stored in the shot file. BLACS then acquires them
    through the same path a real camera's images take, so a lyse script cannot
    tell them apart from a real camera's.
    """

    description = 'Dummy Camera'

    def __init__(self, name, parent_device, connection, serial_number=0x0, **kwargs):
        """A camera that produces images from a function instead of from hardware.

        Args:
            name (str)
                device name

            parent_device (IntermediateDevice)
                Device with digital outputs to be used to trigger acquisition

            connection (str)
                Name of digital output port on parent device.

            serial_number (str or int, optional), default: `0x0`
                A dummy camera identifies no hardware, so this only determines
                what appears as the camera's BLACS connection.

            **kwargs: Further keyword arguments passed to the `__init__` method
                of the parent class (:obj:`TriggerableCamera`). Of these,
                `camera_attributes` determines the images this camera produces:
                `Width` and `Height` give their size in pixels and `PixelFormat`
                gives the depth a pixel saturates at.
        """
        self.image_functions = []
        TriggerableCamera.__init__(
            self, name, parent_device, connection, serial_number, **kwargs
        )
        # Checked here rather than where it is first needed, which is
        # generate_code: a failure there aborts the compile with the shot file
        # already half written, and the half-written file cannot be compiled a
        # second time either.
        sensor_size(self.camera_attributes)

    def expose(
        self,
        t,
        name,
        frametype='frame',
        trigger_duration=None,
        *args,
        function=None,
        **kwargs
    ):
        """Request an exposure, and name the function that produces its image.

        Takes everything :obj:`TriggerableCamera.expose` takes, and then a
        function and the arguments to call it with, in the manner of
        `AnalogQuantity.customramp`: this camera supplies the leading arguments
        and the caller supplies the rest. The function is called as
        `function(X, Y, *args, **kwargs)`, where `X` and `Y` are the camera's
        coordinate grid, and returns an array of counts of that same shape.

        The function is called once per exposure, while the shot compiles. It is
        never stored anywhere -- only the image it returns is -- so it can be
        any callable, including a local one, and nothing needs it on the machine
        BLACS runs on.

        A set of frames that have to agree with each other, such as the atoms,
        probe and dark frames of an absorption image, is three calls to this
        method sharing one function with different arguments. Sharing the
        function is what makes the frames consistent.

        The function is passed by keyword. An exposure given none gets a
        blank frame.
        """
        if callable(trigger_duration):
            msg = """%s was passed where this exposure's trigger duration goes.
                A dummy camera takes its image function by keyword:
                camera.expose(t, name, frametype, function=%s)."""
            name_of = getattr(trigger_duration, '__name__', trigger_duration)
            raise ValueError(dedent(msg) % (name_of, name_of))
        trigger_duration = TriggerableCamera.expose(
            self, t, name, frametype, trigger_duration
        )
        self.image_functions.append((function, args, kwargs))
        return trigger_duration

    def coordinate_grid(self):
        """The meshgrid every one of this camera's image functions is evaluated on.

        Object-plane micrometres, centred on the sensor: the `Width` and `Height`
        pixels in this camera's attributes, scaled by its `pixel_size` and
        `magnification`.
        """
        width, height = sensor_size(self.camera_attributes)
        pixel_x, pixel_y = self.pixel_size
        x = (np.arange(width) - (width - 1) / 2) * pixel_x / self.magnification
        y = (np.arange(height) - (height - 1) / 2) * pixel_y / self.magnification
        return np.meshgrid(x, y)

    def saturation(self):
        """The largest count a pixel of this camera can hold.

        A real camera saturates, so an image function that returns more counts
        than the sensor holds should saturate too rather than wrap around when
        the image is stored. The depth comes from the `PixelFormat` camera
        attribute, which is named for it: `Mono16`, `Mono12`, `Mono8`. A format
        whose name does not end in a number, and one deeper than the uint16
        datasets images are saved in, are both treated as 16-bit.
        """
        pixel_format = str(self.camera_attributes.get('PixelFormat', ''))
        match = re.search(r'(\d+)$', pixel_format)
        bit_depth = int(match.group(1)) if match else DEFAULT_BIT_DEPTH
        return 2 ** min(bit_depth, DEFAULT_BIT_DEPTH) - 1

    def generate_code(self, hdf5_file):
        TriggerableCamera.generate_code(self, hdf5_file)
        if not self.exposures:
            return
        group = hdf5_file['devices'][self.name]
        width, height = sensor_size(self.camera_attributes)
        X, Y = self.coordinate_grid()
        images = []
        # A camera's frames arrive in the order its triggers do, and
        # transition_to_manual matches them up with the exposures sorted by time.
        # Sorting the images the same way is what puts each one under the name
        # and frametype of the exposure that asked for it. Sorting whole
        # exposures rather than their times alone is what makes this the same
        # order: numpy's sort(order='t') breaks ties on the remaining fields, in
        # dtype order, which is what comparing the tuples does.
        for i in sorted(range(len(self.exposures)), key=self.exposures.__getitem__):
            function, args, kwargs = self.image_functions[i]
            if function is None:
                images.append(blank_image(width, height))
                continue
            image = np.asarray(function(X, Y, *args, **kwargs))
            complaint = None
            if image.shape != X.shape:
                complaint = """returned an array of shape %s, but this camera's
                    images are %s. An image function is evaluated on the
                    camera's coordinate grid and must return an array of the
                    same shape as it.""" % (image.shape, X.shape)
            elif not np.isfinite(image).all():
                # np.clip passes a NaN through and the cast to counts is then
                # undefined, so an image that is quietly saturated or quietly
                # black would be stored as though a sensor had read it.
                complaint = """returned an array holding values that are not
                    finite, which cannot be stored as camera counts. Somewhere
                    in it there is a NaN or an infinity."""
            if complaint is not None:
                t, name, frametype, _ = self.exposures[i]
                msg = "%s %s (the '%s' exposure '%s' of %s at t = %s)"
                raise ValueError(
                    msg
                    % (
                        getattr(function, '__name__', function),
                        dedent(complaint),
                        frametype,
                        name,
                        self.name,
                        t,
                    )
                )
            counts = np.clip(image.astype(float), 0, self.saturation())
            images.append(counts.astype(IMAGE_DTYPE))
        group.create_dataset('IMAGES', data=np.array(images), compression='gzip')
