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


import sys
import time
import threading
import numpy as np
import labscript_utils.h5_lock
import h5py
import labscript_utils.properties
import zmq
import time
import json

from zprocess import RichStreamHandler

from blacs.tab_base_classes import Worker

from labscript_utils.shared_drive import path_to_local
import labscript_utils.properties

from ._genicam._genicam import GeniCam

import logging


class GeniCamWorker(Worker):
    # Parameters passing down from BLACS
    # - parent_host
    # - serial_number
    # - cti_file
    # - manual_acquisition_timeout
    # - manual_mode_camera_attributes
    # - camera_attributes
    # - image_receiver_port

    # Camera properties saved in h5 file
    # - stop_acquisition_timeout
    # - exception_on_failed_shot
    # - saved_attribute_visibility_level

    def init(self):
        self.logger = logging.getLogger("BLACS_GeniCam")
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(RichStreamHandler())

        self.camera = GeniCam(self.serial_number, self.cti_file, self.logger)

        self.logger.info("Setting attributes...")
        self.set_attributes(self.camera_attributes)
        self.set_attributes(self.manual_mode_camera_attributes, set_if_changed=True)

        self.default_continuous_polling_interval = 0.01

        self.images = None
        self.n_images = None
        self.attributes_to_save = None
        self.exposures = None
        self.acquisition_thread = None
        self.h5_filepath = None

        self.mode_before_continuous_started = None
        self.continuous_stop = threading.Event()
        self.continuous_thread = None
        self.continuous_dt = None

        self.fetch_image_finished = threading.Event()

        self.zmq_context = zmq.Context()

        self.image_socket = self.zmq_context.socket(zmq.REQ)
        self.image_socket.connect(
            f'tcp://{self.parent_host}:{self.image_receiver_port}'
        )

    def set_attributes(self, attributes, set_if_changed=False):
        return self.camera.feature_tree.set_attributes(attributes, set_if_changed)

    def get_attributes_as_dict(self, visibility=None):
        """Return a dict of the attributes of the camera"""

        attributes_dict = self.camera.feature_tree.dump_value_dict(visibility)

        return attributes_dict

    def get_attribute_tuples_as_dict(self):
        """Return a dict of the FeatureValueTuple of the camera"""

        attributes_dict = self.camera.feature_tree.dump_value_tuple_dict()

        return attributes_dict

    def get_attributes_as_text(self, visibility_level):
        """Return a string representation of the attributes of the camera for
        the given visibility level

        visibility_level: one of "beginner", "expert", or "guru"
        """

        attrs = self.get_attributes_as_dict(visibility_level)
        dict_repr = json.dumps(attrs, indent=4)

        return self.device_name + '_camera_attributes = ' + dict_repr

    def snap(self):
        """Acquire one frame in manual mode. Send it to the parent via
        self.image_socket. Wait for a response from the parent."""

        image = self.camera.snap(self.manual_acquisition_timeout)
        if image is not None:
            self._send_image_to_parent(image)

    def _send_image_to_parent(self, image):
        """Send the image to the GUI to display. This will block if the parent process
        is lagging behind in displaying frames, in order to avoid a backlog."""

        metadata = dict(dtype=str(image.dtype), shape=image.shape)

        self.image_socket.send_json(metadata, zmq.SNDMORE)
        self.image_socket.send(image, copy=False)

        response = self.image_socket.recv()
        assert response == b'ok', response

    def continuous_loop(self, dt):
        """Acquire continuously in a loop, with minimum repetition interval dt"""
        t = time.time()
        while True:
            t = time.time()
            image = self.camera.fetch(self.default_continuous_polling_interval)

            if image is not None:
                self._send_image_to_parent(image)

            if dt is None:
                timeout = 0
            else:
                timeout = t + dt - time.time()

            if self.continuous_stop.wait(timeout):
                self.continuous_stop.clear()
                break

    def start_continuous(self, dt):
        """Begin continuous acquisition in a thread with minimum repetition interval
        dt"""
        # TODO: set and store trigger mode
        assert self.continuous_thread is None
        # self.mode_before_continuous_started = self.camera.feature_tree["Acquisition"]["AcquisitionMode"].feature.value
        # self.camera.feature_tree["Acquisition"]["AcquisitionMode"].feature.value = "Continuous"

        self.camera.start_acquisition()
        self.continuous_thread = threading.Thread(
            target=self.continuous_loop, args=(dt,), daemon=True
        )
        self.continuous_thread.start()
        self.continuous_dt = dt

    def stop_continuous(self, pause=False):
        """Stop the continuous acquisition thread"""
        if not self.continuous_thread:
            return

        # if self.mode_before_continuous_started:
        #     self.camera.feature_tree["Acquisition"]["AcquisitionMode"].feature.value = self.mode_before_continuous_started

        self.continuous_stop.set()
        self.continuous_thread.join()
        self.continuous_thread = None
        self.camera.stop_acquisition()
        # If we're just 'pausing', then do not clear self.continuous_dt. That way
        # continuous acquisition can be resumed with the same interval by calling
        # start(self.continuous_dt), without having to get the interval from the parent
        # again, and the fact that self.continuous_dt is not None can be used to infer
        # that continuous acquisiton is paused and should be resumed after a buffered
        # run is complete:
        if not pause:
            self.continuous_dt = None

    def transition_to_buffered(self, device_name, h5_filepath, initial_values, fresh):
        if getattr(self, 'is_remote', False):
            h5_filepath = path_to_local(h5_filepath)

        if self.continuous_thread is not None:
            # Pause continuous acquistion during transition_to_buffered:
            self.stop_continuous(pause=True)

        with h5py.File(h5_filepath, 'r') as f:
            group = f['devices'][self.device_name]
            if not 'EXPOSURES' in group:
                return {}

            self.h5_filepath = h5_filepath
            self.exposures = group['EXPOSURES'][:]
            self.n_images = len(self.exposures)

            # Get the camera_attributes from the device_properties
            properties = labscript_utils.properties.get(
                f, self.device_name, 'device_properties'
            )

            camera_attributes = properties['camera_attributes']
            self.stop_acquisition_timeout = properties['stop_acquisition_timeout']
            self.exception_on_failed_shot = properties['exception_on_failed_shot']
            saved_attr_level = properties['saved_attribute_visibility_level']

        self.camera.raise_exception_on_failed_shot = self.exception_on_failed_shot

        # Only reprogram attributes that differ from those last programmed in, or all of
        # them if a fresh reprogramming was requested:
        self.set_attributes(camera_attributes, set_if_changed=(not fresh))

        # Get the camera attributes, so that we can save them to the H5 file:
        if saved_attr_level is not None:
            self.attributes_to_save = self.get_attributes_as_dict(saved_attr_level)
        else:
            self.attributes_to_save = None

        self.logger.info(f"Configuring camera for {self.n_images} images.")

        self.fetch_image_finished.clear()

        # self.camera.feature_tree["Acquisition"]["AcquisitionMode"].feature.value = "MultiFrame"
        self.camera.feature_tree["Acquisition"]["AcquisitionFrameCount"].feature.value = self.n_images

        self.camera.start_acquisition()

        self.acquisition_thread = threading.Thread(
            target=self.camera.fetch_n_images,
            args=(self.n_images, self._image_fetch_callback, self.stop_acquisition_timeout),
            daemon=True,
        )

        self.acquisition_thread.start()
        return {}

    def _image_fetch_callback(self, images):
        self.images = images
        self.fetch_image_finished.set()

    def transition_to_manual(self):
        if self.h5_filepath is None:
            self.logger.info('No camera exposures in this shot.\n')
            return True

        assert self.acquisition_thread is not None

        if self.fetch_image_finished.wait(self.stop_acquisition_timeout):
            self.fetch_image_finished.clear()
        else:

            emsg = ("Acquisition thread did not finish. Likely did not acquire expected"
                    "number of images. Check triggering is connected/configured correctly.")

            if self.exception_on_failed_shot:
                self.abort()
                raise RuntimeError(emsg)
            else:
                self.camera.abort_acquisition()
                self.acquisition_thread.join()
                self.logger.error(emsg)

        self.acquisition_thread = None

        self.logger.debug("Stop acquisition...")
        self.camera.stop_acquisition()

        self.logger.debug(f"Saving {len(self.images)}/{len(self.exposures)} images...")

        with h5py.File(self.h5_filepath, 'r+') as f:
            image_path = 'images/' + self.device_name
            image_group = f.require_group(image_path)
            image_group.attrs['camera'] = self.device_name

            # Save camera attributes to the HDF5 file:
            if self.attributes_to_save is not None:
                labscript_utils.properties.set_attributes(image_group, self.attributes_to_save)

            # Whether we failed to get all the expected exposures:
            image_group.attrs['failed_shot'] = len(self.images) != len(self.exposures)

            # key the images by name and frametype. Allow for the case of there being
            # multiple images with the same name and frametype. In this case we will
            # save an array of images in a single dataset.
            images = {
                (exposure['name'], exposure['frametype']): []
                for exposure in self.exposures
            }

            # Iterate over expected exposures, sorted by acquisition time, to match them
            # up with the acquired images:
            self.exposures.sort(order='t')
            for image, exposure in zip(self.images, self.exposures):
                images[(exposure['name'], exposure['frametype'])].append(image)

            # Save images to the HDF5 file:
            for (name, frametype), imagelist in images.items():
                data = imagelist[0] if len(imagelist) == 1 else np.array(imagelist)
                self.logger.debug(f"Saving frame(s) {name}/{frametype}.")
                group = image_group.require_group(name)
                dset = group.create_dataset(
                    frametype, data=data.astype('uint16'), dtype='uint16', compression='gzip'
                )
                # Specify this dataset should be viewed as an image
                dset.attrs['CLASS'] = np.string_('IMAGE')
                dset.attrs['IMAGE_VERSION'] = np.string_('1.2')
                dset.attrs['IMAGE_SUBCLASS'] = np.string_('IMAGE_GRAYSCALE')
                dset.attrs['IMAGE_WHITE_IS_ZERO'] = np.uint8(0)

        self.logger.info(f"{len(self.images)} images saved.")

        # If the images are all the same shape, send them to the GUI for display:
        try:
            image_block = np.stack(self.images)
        except ValueError:
            self.logger.warning("Cannot display images in the GUI, they are not all the same shape")
        else:
            self._send_image_to_parent(image_block)

        self.images = None
        self.n_images = None
        self.attributes_to_save = None
        self.exposures = None
        self.h5_filepath = None
        self.stop_acquisition_timeout = None
        self.exception_on_failed_shot = None

        self.logger.info("Setting manual mode camera attributes.\n")

        self.set_attributes(self.manual_mode_camera_attributes, set_if_changed=True)
        if self.continuous_dt is not None:
            # If continuous manual mode acquisition was in progress before the bufferd
            # run, resume it:
            self.start_continuous(self.continuous_dt)
        return True

    def abort(self):
        if self.acquisition_thread is not None:
            self.camera.abort_acquisition()
            self.acquisition_thread.join()
            self.acquisition_thread = None
            self.camera.stop_acquisition()

        self.camera._abort_acquisition = False
        self.images = None
        self.n_images = None
        self.attributes_to_save = None
        self.exposures = None
        self.acquisition_thread = None
        self.h5_filepath = None
        self.stop_acquisition_timeout = None
        self.exception_on_failed_shot = None

        # Resume continuous acquisition, if any:
        if self.continuous_dt is not None and self.continuous_thread is None:
            self.start_continuous(self.continuous_dt)
        return True

    def abort_buffered(self):
        return self.abort()

    def abort_transition_to_buffered(self):
        return self.abort()

    def program_manual(self, values):
        return {}

    def shutdown(self):
        if self.continuous_thread is not None:
            self.stop_continuous()

        self.image_socket.close()  # forgetting to close the socket will crash blacs when restarting worker
        self.camera.close()
