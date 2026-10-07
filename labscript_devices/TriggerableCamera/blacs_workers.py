#####################################################################
#                                                                   #
# /labscript_devices/TriggerableCamera/blacs_workers.py             #
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
from time import perf_counter
from blacs.tab_base_classes import Worker
import threading
import numpy as np
from labscript_utils import dedent
import labscript_utils.h5_lock
import h5py
import labscript_utils.properties
import zmq

from labscript_utils.ls_zprocess import Context
from labscript_utils.shared_drive import path_to_local
from labscript_utils.properties import set_attributes


def _unwritten(camera, method):
    """The message for a member of the camera contract a camera has not written."""
    msg = """%s does not implement %s(). A camera interface class implements
        every member of the contract in TriggerableCameraInterface, or
        overrides the method that reaches for it."""
    return dedent(msg) % (type(camera).__name__, method)


class TriggerableCameraInterface(object):
    """The object a camera worker talks to in place of hardware.

    One of these is what :obj:`TriggerableCameraWorker.interface_class` names,
    and every camera in labscript_devices implements it: a thin layer over one
    vendor's API, holding no labscript state and knowing nothing about shots.

    The worker calls `set_attributes`, `get_attributes_as_dict`, `snap`,
    `grab`, `grab_multiple`, `configure_acquisition`, `stop_acquisition`,
    `abort_acquisition` and `close`. `snap` is called with no acquisition
    configured and must arrange its own; `grab` is called only between
    `configure_acquisition` and `stop_acquisition`. An array returned by either
    must stay valid after the next one is taken, since `grab_multiple`
    accumulates them, which is why most cameras copy out of the vendor's
    buffer.

    A camera should subclass this. It then gets `grab_multiple`,
    `abort_acquisition` and the composing `get_attributes_as_dict` for free,
    and is told which member it has forgotten rather than failing with an
    AttributeError deep in a shot. One that does not must write every member
    the worker calls, except that a worker subclassing `IMAQdxCameraWorker`
    builds `get_attributes_as_dict` for it, a route that is deprecated.
    """

    # The worker overwrites this on every buffered shot, from the device
    # property of the same name. The value here is what a manual-mode
    # acquisition sees before any shot has run.
    exception_on_failed_shot = True

    # Polled by grab_multiple between frames, set by abort_acquisition from
    # whichever thread aborts, and cleared by the worker once it has joined the
    # acquisition thread.
    _abort_acquisition = False

    # The members a camera writes for itself. Each raises rather than doing
    # nothing, because a camera that silently fails to program an attribute or
    # stop an acquisition is worse than one that does not start. All but the
    # two attribute readers are owed by every camera; those two are owed only
    # by a camera that inherits the composing `get_attributes_as_dict` below.

    def set_attributes(self, attributes):
        """Program a dict of attribute names and values into the camera."""
        raise NotImplementedError(_unwritten(self, 'set_attributes'))

    def get_attribute(self, name):
        """Return the current value of the named attribute."""
        raise NotImplementedError(_unwritten(self, 'get_attribute'))

    def get_attribute_names(self, visibility_level):
        """Return the names of the attributes at the given level of detail."""
        raise NotImplementedError(_unwritten(self, 'get_attribute_names'))

    def snap(self):
        """Acquire and return one image, configuring acquisition as needed."""
        raise NotImplementedError(_unwritten(self, 'snap'))

    def grab(self):
        """Return the next image of an acquisition already configured."""
        raise NotImplementedError(_unwritten(self, 'grab'))

    def configure_acquisition(self, continuous=True, bufferCount=None):
        """Ready the camera to be grabbed from.

        The worker calls this with no arguments for manual-mode continuous
        acquisition, and with `continuous=False` and a `bufferCount` of the
        shot's exposures for a buffered one.
        """
        raise NotImplementedError(_unwritten(self, 'configure_acquisition'))

    def stop_acquisition(self):
        """End an acquisition. Called after a shot, a failed shot and an abort,
        so it has to be safe when nothing is acquiring."""
        raise NotImplementedError(_unwritten(self, 'stop_acquisition'))

    def close(self):
        """Release the camera. The worker calls this when it shuts down."""
        raise NotImplementedError(_unwritten(self, 'close'))

    # Reading the attributes back, for the shot file and the BLACS dialog.

    def get_attributes_as_dict(self, visibility_level):
        """Return a dict of the camera's attributes at the given level of detail.

        Composed here from `get_attribute_names` and `get_attribute`, which is
        what a camera whose API is read one attribute at a time wants. A camera
        whose API hands over every attribute in one call overrides this and
        owes neither of those two.
        """
        names = self.get_attribute_names(visibility_level)
        return {name: self.get_attribute(name) for name in names}

    # Acquiring a shot's worth of frames.

    def is_transient_grab_error(self, exception):
        """Whether this exception from `grab` means "no frame yet, ask again".

        A camera waiting for a trigger reports the wait as an error, and the
        acquisition has to keep asking: the shot decides when the triggers
        arrive, and how long that takes is not the camera's business. Anything
        else is a real failure. A camera whose `grab` blocks until a frame
        arrives, or which cannot tell a wait from a failure, says False to
        everything and is never retried.

        The retry is paced by `grab` and by nothing else: a camera that says
        True here must block for its own timeout before reporting the wait,
        because the loop asks again immediately. One that returns straight
        away would spin a core until the shot times out.
        """
        return False

    def is_skippable_grab_error(self, exception):
        """Whether `exception_on_failed_shot` may skip past this exception.

        An error the camera's own API reported, as against a fault in the code
        driving it. When a camera says True here and the shot was configured
        with `exception_on_failed_shot=False`, the frame is given up and the
        acquisition moves to the next exposure rather than failing the shot.
        """
        return False

    def abort_acquisition(self):
        """Ask an acquisition in progress to stop.

        Called from the worker's thread while `grab_multiple` runs in its own,
        so this only raises the flag; the loop sees it between frames. A camera
        whose `grab` blocks in the vendor's API overrides this to make the call
        that unblocks it, and then calls this implementation.
        """
        self._abort_acquisition = True

    def grab_multiple(self, n_images, images):
        """Grab `n_images` frames, appending each to `images` as it arrives.

        The worker runs this in a thread for the duration of a shot, having
        configured the acquisition for the same `n_images`, so a camera that
        allocates its buffers up front has one per frame asked for. A camera
        whose acquisition is not one frame per `grab` -- a kinetic series, say
        -- overrides this wholesale rather than bending the loop around it.
        """
        print(f"Attempting to grab {n_images} images.")
        for i in range(n_images):
            while True:
                if self._abort_acquisition:
                    print("Abort during acquisition.")
                    self._abort_acquisition = False
                    return
                try:
                    image = self.grab()
                except Exception as exception:
                    if self.is_transient_grab_error(exception):
                        print('.', end='')
                        continue
                    if (
                        self.is_skippable_grab_error(exception)
                        and not self.exception_on_failed_shot
                    ):
                        print(exception, file=sys.stderr)
                        break
                    raise
                images.append(image)
                print(f"Got image {i+1} of {n_images}.")
                break
        print(f"Got {len(images)} of {n_images} images.")


class TriggerableCameraWorker(Worker):
    # The camera interface class this worker drives. Subclasses name their own
    # here if it takes only the serial number as an instantiation argument,
    # otherwise they reimplement get_camera():
    interface_class = None

    def init(self):
        # get_attributes_as_dict is called on the camera, so a worker that
        # overrides it would have the override skipped without a word.
        for cls in type(self).__mro__:
            if cls is TriggerableCameraWorker:
                break
            if 'get_attributes_as_dict' in vars(cls):
                raise RuntimeError(
                    f"{cls.__name__} overrides get_attributes_as_dict(), which is "
                    "called on the camera, not the worker. Move it to the camera class."
                )
        self.camera = self.get_camera()
        print("Setting attributes...")
        self.smart_cache = {}
        self.set_attributes_smart(self.camera_attributes)
        self.set_attributes_smart(self.manual_mode_camera_attributes)
        print("Initialisation complete")
        self._clear_shot_state()
        self.continuous_stop = threading.Event()
        self.continuous_thread = None
        self.continuous_dt = None
        self.image_socket = Context().socket(zmq.REQ)
        self.image_socket.connect(
            f'tcp://{self.parent_host}:{self.image_receiver_port}'
        )

    def _clear_shot_state(self):
        """Forget the shot just finished, or the one that never started."""
        self.images = None
        self.n_images = None
        self.attributes_to_save = None
        self.exposures = None
        self.acquisition_thread = None
        self.h5_filepath = None
        self.stop_acquisition_timeout = None
        self.exception_on_failed_shot = None

    def get_camera(self):
        """Return an instance of the camera interface class. Subclasses may override
        this method to pass required arguments to their class if they require more
        than just the serial number."""
        if self.interface_class is None:
            msg = """%s names no interface class. A camera worker sets
                interface_class to the class that talks to its camera, or
                reimplements get_camera()."""
            raise NotImplementedError(dedent(msg) % type(self).__name__)
        return self.interface_class(self.serial_number)

    def load_shot_data(self, shot_file):
        """Read whatever else this worker needs from the shot file.

        Called from transition_to_buffered with the shot file open, once the
        exposures and the camera attributes have been read from it. A camera
        that needs more of the shot than those overrides this, rather than
        opening and locking the file a second time.
        """
        pass

    def set_attributes_smart(self, attributes):
        """Call self.camera.set_attributes() to set the given attributes, only setting
        those that differ from their value in, or are absent from self.smart_cache.
        Update self.smart_cache with the newly-set values"""
        uncached_attributes = {}
        for name, value in attributes.items():
            if name not in self.smart_cache or self.smart_cache[name] != value:
                uncached_attributes[name] = value
                self.smart_cache[name] = value
        self.camera.set_attributes(uncached_attributes)

    def get_attributes_as_text(self, visibility_level):
        """Return a string representation of the attributes of the camera for
        the given visibility level"""
        attrs = self.camera.get_attributes_as_dict(visibility_level)
        # Format it nicely:
        lines = [f'    {repr(key)}: {repr(value)},' for key, value in attrs.items()]
        dict_repr = '\n'.join(['{'] + lines + ['}'])
        return self.device_name + '_camera_attributes = ' + dict_repr

    def snap(self):
        """Acquire one frame in manual mode. Send it to the parent via
        self.image_socket. Wait for a response from the parent."""
        image = self.camera.snap()
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
        while True:
            if dt is not None:
                t = perf_counter()
            image = self.camera.grab()
            self._send_image_to_parent(image)
            if dt is None:
                timeout = 0
            else:
                timeout = t + dt - perf_counter()
            if self.continuous_stop.wait(timeout):
                self.continuous_stop.clear()
                break

    def start_continuous(self, dt):
        """Begin continuous acquisition in a thread with minimum repetition interval
        dt"""
        assert self.continuous_thread is None
        self.camera.configure_acquisition()
        self.continuous_thread = threading.Thread(
            target=self.continuous_loop, args=(dt,), daemon=True
        )
        self.continuous_thread.start()
        self.continuous_dt = dt

    def stop_continuous(self, pause=False):
        """Stop the continuous acquisition thread"""
        assert self.continuous_thread is not None
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
            self.camera.exception_on_failed_shot = self.exception_on_failed_shot
            self.load_shot_data(f)
        # Only reprogram attributes that differ from those last programmed in, or all of
        # them if a fresh reprogramming was requested:
        if fresh:
            self.smart_cache = {}
        self.set_attributes_smart(camera_attributes)
        # Get the camera attributes, so that we can save them to the H5 file:
        if saved_attr_level is not None:
            self.attributes_to_save = self.camera.get_attributes_as_dict(
                saved_attr_level
            )
        else:
            self.attributes_to_save = None
        print(f"Configuring camera for {self.n_images} images.")
        self.camera.configure_acquisition(continuous=False, bufferCount=self.n_images)
        self.images = []
        self.acquisition_thread = threading.Thread(
            target=self.camera.grab_multiple,
            args=(self.n_images, self.images),
            daemon=True,
        )
        self.acquisition_thread.start()
        return {}

    def transition_to_manual(self):
        if self.h5_filepath is None:
            print('No camera exposures in this shot.\n')
            return True
        assert self.acquisition_thread is not None
        self.acquisition_thread.join(timeout=self.stop_acquisition_timeout)
        if self.acquisition_thread.is_alive():
            msg = """Acquisition thread did not finish. Likely did not acquire expected
                number of images. Check triggering is connected/configured correctly"""
            if self.exception_on_failed_shot:
                self.abort()
                raise RuntimeError(dedent(msg))
            else:
                self.camera.abort_acquisition()
                self.acquisition_thread.join()
                print(dedent(msg), file=sys.stderr)
        self.acquisition_thread = None

        print("Stopping acquisition.")
        self.camera.stop_acquisition()

        print(f"Saving {len(self.images)}/{len(self.exposures)} images.")

        with h5py.File(self.h5_filepath, 'r+') as f:
            # Use orientation for image path, device_name if orientation unspecified
            if self.orientation is not None:
                image_path = 'images/' + self.orientation
            else:
                image_path = 'images/' + self.device_name
            image_group = f.require_group(image_path)
            image_group.attrs['camera'] = self.device_name

            # Save camera attributes to the HDF5 file:
            if self.attributes_to_save is not None:
                set_attributes(image_group, self.attributes_to_save)

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
                print(f"Saving frame(s) {name}/{frametype}.")
                group = image_group.require_group(name)
                dset = group.create_dataset(
                    frametype, data=data, dtype='uint16', compression='gzip'
                )
                # Specify this dataset should be viewed as an image
                dset.attrs['CLASS'] = np.bytes_('IMAGE')
                dset.attrs['IMAGE_VERSION'] = np.bytes_('1.2')
                dset.attrs['IMAGE_SUBCLASS'] = np.bytes_('IMAGE_GRAYSCALE')
                dset.attrs['IMAGE_WHITE_IS_ZERO'] = np.uint8(0)

        # If the images are all the same shape, send them to the GUI for display:
        try:
            image_block = np.stack(self.images)
        except ValueError:
            print("Cannot display images in the GUI, they are not all the same shape")
        else:
            self._send_image_to_parent(image_block)

        self._clear_shot_state()
        print("Setting manual mode camera attributes.\n")
        self.set_attributes_smart(self.manual_mode_camera_attributes)
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
        self._clear_shot_state()
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
        self.camera.close()
