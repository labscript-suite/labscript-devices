#####################################################################
#                                                                   #
# /labscript_devices/GenICamCamera/blacs_workers.py                 #
#                                                                   #
# Copyright 2026, Christopher Billington                            #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
import os
import sys
from pathlib import Path

import numpy as np

from labscript_devices.common.triggerable_camera.blacs_workers import (
    CameraInterface,
    MockCamera,
    TriggerableCameraWorker,
)

# Imported by GenICam_Camera, so that this module imports without harvesters installed
TimeoutException = None

# GenICam visibility (Beginner, Expert, Guru) of the most detailed attributes at each
# visibility level
VISIBILITIES = {'simple': 0, 'intermediate': 1, 'advanced': 2}

# genicam.genapi.EInterfaceType of Integer, Boolean, Float, String and Enumeration nodes
VALUE_INTERFACE_TYPES = {2, 3, 5, 6, 9}

# genicam.genapi.EAccessMode
READ_ONLY = 3
READ_WRITE = 4

# The dtype of the images in each pixel format
PIXEL_FORMATS = {
    'Mono8': np.uint8,
    'Mono10': np.uint16,
    'Mono12': np.uint16,
    'Mono14': np.uint16,
    'Mono16': np.uint16,
}


def producer_files():
    """Return the GenTL producers in the directories of GENICAM_GENTL64_PATH"""
    directories = os.environ.get('GENICAM_GENTL64_PATH', '').split(os.pathsep)
    return [str(p) for d in directories if d for p in sorted(Path(d).glob('*.cti'))]


class GenICam_Camera(CameraInterface):
    # Timeout in seconds of grab(), and of each attempt of grab_multiple() to get an
    # image, after which it checks whether the acquisition has been aborted:
    timeout = 5
    grab_multiple_timeout = 0.5

    def __init__(self, serial_number, cti_file):
        super().__init__()
        global TimeoutException
        from harvesters.core import Harvester
        from genicam.gentl import TimeoutException

        self.harvester = Harvester()
        cti_files = [cti_file] if cti_file is not None else producer_files()
        if not cti_files:
            msg = "No cti_file given, and no GenTL producer in GENICAM_GENTL64_PATH"
            raise RuntimeError(msg)
        for path in cti_files:
            self.harvester.add_file(path, check_existence=True)
        self.harvester.update()
        serial_numbers = [d.serial_number for d in self.harvester.device_info_list]
        if serial_number not in serial_numbers:
            self.harvester.reset()
            msg = f"""No camera with serial number {serial_number!r} found. Cameras
                found: {serial_numbers}"""
            raise RuntimeError(' '.join(msg.split()))
        self.acquirer = self.harvester.create({'serial_number': serial_number})
        self.node_map = self.acquirer.remote_device.node_map

    def set_attribute(self, name, value):
        try:
            self.node_map.get_node(name).value = value
        except Exception as e:
            raise Exception(f"failed to set attribute {name} to {value}") from e

    def get_attribute_names(self, visibility_level, writeable_only=True):
        max_visibility = VISIBILITIES[visibility_level.lower()]
        access_modes = {READ_WRITE} if writeable_only else {READ_ONLY, READ_WRITE}
        names = []
        for feature in self.node_map._get_nodes():
            node = feature.node
            if (
                node.principal_interface_type in VALUE_INTERFACE_TYPES
                and node.visibility <= max_visibility
                and feature.get_access_mode() in access_modes
            ):
                names.append(node.name)
        return names

    def get_attribute(self, name):
        try:
            return self.node_map.get_node(name).value
        except Exception as e:
            raise Exception(f"Failed to get attribute {name}") from e

    def snap(self):
        self.configure_acquisition(continuous=False, bufferCount=1)
        try:
            return self.grab()
        finally:
            self.stop_acquisition()

    def configure_acquisition(self, continuous=True, bufferCount=5):
        self.acquirer.num_buffers = max(bufferCount, self.acquirer.min_num_buffers)
        self.acquirer.start()

    def grab(self, timeout=None):
        with self.acquirer.fetch(timeout=timeout or self.timeout) as buffer:
            component = buffer.payload.components[0]
            if component.data_format not in PIXEL_FORMATS:
                msg = f"""Pixel format {component.data_format} is not supported. Set
                    'PixelFormat' in camera_attributes to one of {list(PIXEL_FORMATS)}"""
                raise ValueError(' '.join(msg.split()))
            dtype = PIXEL_FORMATS[component.data_format]
            shape = (component.height, component.width)
            return component.data.astype(dtype, copy=True).reshape(shape)

    def grab_multiple(self, n_images, images):
        print(f"Attempting to grab {n_images} images.")
        for i in range(n_images):
            while True:
                if self._abort_acquisition:
                    print("Abort during acquisition.")
                    self._abort_acquisition = False
                    return
                try:
                    images.append(self.grab(self.grab_multiple_timeout))
                    print(f"Got image {i+1} of {n_images}.")
                    break
                except TimeoutException:
                    print('.', end='')
                    continue
                except Exception as e:
                    if self.exception_on_failed_shot:
                        raise
                    print(e, file=sys.stderr)
                    return
        print(f"Got {len(images)} of {n_images} images.")

    def stop_acquisition(self):
        self.acquirer.stop()

    def close(self):
        self.acquirer.destroy()
        self.harvester.reset()


class GenICamCameraWorker(TriggerableCameraWorker):
    interface_class = GenICam_Camera

    def get_camera(self):
        if self.mock:
            return MockCamera()
        return self.interface_class(self.serial_number, self.cti_file)
