#####################################################################
#                                                                   #
# /labscript_devices/DummyCamera/blacs_workers.py                   #
#                                                                   #
# Copyright 2026, Ian Spielman and contributors                     #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
import sys

import numpy as np
import labscript_utils.h5_lock
import h5py
from labscript_utils.shared_drive import path_to_local

from labscript_devices.common.triggerable_camera.blacs_workers import (
    CameraInterface,
    TriggerableCameraWorker,
)


class Dummy_Camera(CameraInterface):
    """A camera that returns the images of the shot, which were computed when the shot
    was compiled, and zero images in manual mode."""

    mock_data = True

    def __init__(self, serial_number):
        super().__init__()
        self.attributes = {}
        self.shot_images = None
        self.images = None
        self.next_image = 0

    def set_attribute(self, name, value):
        self.attributes[name] = value

    def get_attribute_names(self, visibility_level):
        return list(self.attributes)

    def get_attribute(self, name):
        return self.attributes[name]

    def load_images(self, images):
        """Set the images to return during the next acquisition that is not
        continuous"""
        self.shot_images = images

    def snap(self):
        return np.zeros(
            (self.attributes['Height'], self.attributes['Width']), dtype=np.uint16
        )

    def configure_acquisition(self, continuous=True, bufferCount=5):
        self.images = None if continuous else self.shot_images
        self.next_image = 0

    def grab(self):
        if self.images is None:
            return self.snap()
        if self.next_image == len(self.images):
            raise RuntimeError(f"The shot has only {len(self.images)} images")
        image = self.images[self.next_image]
        self.next_image += 1
        return image

    def grab_multiple(self, n_images, images):
        for _ in range(n_images):
            if self._abort_acquisition:
                print("Abort during acquisition.")
                self._abort_acquisition = False
                return
            try:
                images.append(self.grab())
            except RuntimeError as e:
                if self.exception_on_failed_shot:
                    raise
                print(e, file=sys.stderr)
                return
        print(f"Got {len(images)} of {n_images} images.")

    def stop_acquisition(self):
        self.images = None

    def close(self):
        pass


class DummyCameraWorker(TriggerableCameraWorker):
    interface_class = Dummy_Camera

    def transition_to_buffered(self, device_name, h5_filepath, initial_values, fresh):
        local_filepath = h5_filepath
        if getattr(self, 'is_remote', False):
            local_filepath = path_to_local(h5_filepath)
        with h5py.File(local_filepath, 'r') as f:
            group = f['devices'][self.device_name]
            self.camera.load_images(group['IMAGES'][:] if 'IMAGES' in group else None)
        return super().transition_to_buffered(
            device_name, h5_filepath, initial_values, fresh
        )
