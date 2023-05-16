from harvesters.core import Harvester
from genicam.genapi import NodeMap
from genicam.genapi import EInterfaceType, EAccessMode, EVisibility
from genicam.gentl import TimeoutException, GenericException

import time
import logging
import numpy as np

from ._feature_tree import GeniCamFeatureTreeNode


def nested_get(dct, keys):
    for key in keys:
        dct = dct[key]
    return dct


class GeniCamException(Exception):
    pass


class GeniCam:
    _readable_nodes = [
        EInterfaceType.intfIBoolean,
        EInterfaceType.intfIEnumeration,
        EInterfaceType.intfIFloat,
        EInterfaceType.intfIInteger,
        EInterfaceType.intfIString,
        EInterfaceType.intfIRegister,
    ]

    _readable_access_modes = [EAccessMode.RW, EAccessMode.RO]

    def __init__(self, serial_number, cti_path, logger=None):
        self.logger = logger if logger else logging.getLogger()

        self.raise_exception_on_failed_shot = False
        self._image_fetch_polling_interval = 0.01  ## c.f. harvesters/core.py, `_timeout_on_client_fetch_call`

        self.harvester = Harvester()

        self.harvester.add_file(cti_path, check_validity=True)
        self.harvester.update()

        self.ia = None

        try:
            self.ia = self.harvester.create({'serial_number': serial_number})
        except IndexError:
            logging.error(f"Couldn't not find camera with serial number {serial_number}. List of available cameras:")
            logging.error(self.harvester.device_info_list)

            raise GeniCamException(f"Couldn't not find camera with serial number {serial_number}.")

        self.feature_tree = GeniCamFeatureTreeNode.get_tree_from_genicam_root_node(
                self.ia.remote_device.node_map.Root)

        self._abort_acquisition = False

    def snap(self, timeout):
        mode_feat = self.feature_tree["Acquisition"]["AcquisitionMode"].data
        old_mode = mode_feat.value
        mode_feat.value = "SingleFrame"

        self.ia.start()
        img = self.fetch(timeout=timeout)
        self.ia.stop()

        mode_feat.value = old_mode

        if img is None:
            raise Exception("Acqusition timeout.")

        return img

    def fetch(self, timeout: float =0, raise_when_timeout=False):
        try:
            with self.ia.fetch(timeout=timeout) as buffer:
                component = buffer.payload.components[0]
                data = np.copy(component.data)
                _2d = data.reshape(component.height, component.width)

                return _2d
        except TimeoutException as e:
            if raise_when_timeout:
                raise e
            return None

    def fetch_n_images(self, n_images, callback=None, timeout=0):
        self._abort_acquisition = False

        images = []

        base = time.time()

        poll_timeout = 100e-6  # polling every 100us

        self.logger.debug(f"Polling for {n_images} images...")
        for i in range(n_images):
            while True:
                elapsed = time.time() - base
                if self._abort_acquisition:
                    self.logger.info("Received abort signal during acquisition.")
                    self._abort_acquisition = False
                    if callback:
                        callback(images)

                        return images

                if timeout and elapsed > timeout:
                    raise Exception(f"Acqusition timeout while waiting for the {i+1}/{n_images} image.")

                try:
                    img = self.fetch(poll_timeout, True)
                    break
                except TimeoutException:
                    continue
                except GenericException as e:
                    if self.raise_exception_on_failed_shot:
                        raise e
                    else:
                        self.logger.error(f"Error when acquiring image {i+1}/{n_images}:")
                        self.logger.exception(e)

            if img is not None:
                images.append(img)
                self.logger.debug(f"Received image {i+1}/{n_images}.")

        self.logger.debug(f"Received all {n_images} images.")

        if callback:
            callback(images)

        return images

    def stop_acquisition(self):
        self.ia.stop()

    def start_acquisition(self):
        self._abort_acquisition = False
        self.ia.start()

    def abort_acquisition(self):
        self._abort_acquisition = True
        self.ia.stop()

    def close(self):
        if self.ia:
            self.ia.destroy()

