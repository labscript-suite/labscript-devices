#####################################################################
#                                                                   #
# /labscript_devices/ThorlabsTSICamera/blacs_workers.py             #
#                                                                   #
# Copyright 2026, Christopher Billington                            #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

import sys
import time
import atexit
import tempfile
import threading
from pathlib import Path
from time import perf_counter

from filelock import FileLock, Timeout
import labscript_utils.h5_lock
import h5py
import labscript_utils.properties
from labscript_utils.shared_drive import path_to_local

from labscript_devices.IMAQdxCamera.blacs_workers import IMAQdxCameraWorker

# Version of the thorlabs_tsi_sdk package in Thorlabs camera SDK 2.3:
MIN_SDK_VERSION = (1, 2, 0)

# Attributes added at each visibility level. Each level also has the attributes of the
# levels before it. All but bulb_mode are properties of thorlabs_tsi_sdk's TLCamera.
VISIBILITY_LEVEL_ATTRIBUTES = {
    'simple': ['exposure_time_us', 'gain', 'roi', 'binx', 'biny', 'bulb_mode'],
    'intermediate': [
        'black_level',
        'data_rate',
        'is_frame_rate_control_enabled',
        'frame_rate_control_value',
        'is_led_on',
    ],
    'advanced': [
        'is_hot_pixel_correction_enabled',
        'hot_pixel_correction_threshold',
        'is_eep_enabled',
    ],
}

# Attributes that are enums in the SDK, with the names of their enum classes in
# thorlabs_tsi_sdk.tl_camera_enums. Their values are the names of the enum members.
ENUM_ATTRIBUTES = {'data_rate': 'DATA_RATE'}


class CameraLock:
    """A lock that a process holds while it has the camera with the given serial number
    open. It is an operating system lock on a file in the temporary directory, so it is
    released when the process exits, however it exits. Other programs can take the same
    lock with `filelock.FileLock` on the same file."""

    def __init__(self, serial_number):
        self.serial_number = serial_number
        path = Path(tempfile.gettempdir()) / f'thorlabs-tsi-camera-{serial_number}.lock'
        self._lock = FileLock(path, thread_local=False)

    def acquire(self):
        try:
            self._lock.acquire(timeout=0)
        except Timeout:
            msg = f"Thorlabs camera {self.serial_number} is in use by another process"
            raise RuntimeError(msg) from None

    def release(self):
        self._lock.release()


_sdk = None
_sdk_lock = threading.Lock()


def _get_sdk():
    """Return the process's TLCameraSDK instance, which is created on first use. The SDK
    is opened only once per process, because opening it again in a process that has
    closed it can hang."""
    global _sdk
    with _sdk_lock:
        if _sdk is None:
            import thorlabs_tsi_sdk.version
            from thorlabs_tsi_sdk.tl_camera import TLCameraSDK

            version = thorlabs_tsi_sdk.version.version_number
            if tuple(int(n) for n in version.split('.')) < MIN_SDK_VERSION:
                msg = f"""thorlabs_tsi_sdk {version} is installed. Version 1.2.0 or
                    later, which is in Thorlabs camera SDK 2.3 and later, is required"""
                raise RuntimeError(' '.join(msg.split()))
            _sdk = TLCameraSDK()
            atexit.register(_dispose_sdk)
        return _sdk


def _dispose_sdk():
    with _sdk_lock:
        if _sdk is not None:
            _sdk.dispose()


class ThorlabsTSICamera(object):
    """Interface to a Thorlabs scientific camera through the thorlabs_tsi_sdk package.

    The camera stays armed between hardware-triggered acquisitions. It is disarmed when
    an attribute is set, when an acquisition with a different configuration is
    configured, and when the camera is closed. Frames left over from a previous
    acquisition are discarded when the next acquisition is configured. Calls into the
    SDK are serialised with a lock, so methods may be called from any thread."""

    # Number of image buffers that the camera is armed with, unless an acquisition
    # requires more. The number is never reduced.
    MIN_BUFFER_COUNT = 16

    # Time in seconds that grab() waits for a frame, in addition to the exposure and
    # readout time, or the frame interval if the frame rate is controlled.
    GRAB_TIMEOUT_MARGIN = 1.0

    # Interval in seconds at which we poll the SDK for a pending frame
    GRAB_POLL_INTERVAL = 0.001

    def __init__(self, serial_number, logger):
        from thorlabs_tsi_sdk.tl_camera import TLCameraError
        from thorlabs_tsi_sdk import tl_camera_enums

        self._TLCameraError = TLCameraError
        self._enums = tl_camera_enums
        self.serial_number = str(serial_number)
        self.logger = logger
        self._lock = threading.RLock()
        self.cam = None
        self.camera_lock = CameraLock(self.serial_number)
        self.camera_lock.acquire()
        try:
            sdk = _get_sdk()
            serial_numbers = sdk.discover_available_cameras()
            if self.serial_number not in serial_numbers:
                msg = f"""No Thorlabs camera with serial number {self.serial_number}
                    found. Connected cameras: {serial_numbers}"""
                raise ValueError(' '.join(msg.split()))
            self.cam = sdk.open_camera(self.serial_number)
        except BaseException:
            self.camera_lock.release()
            self.camera_lock = None
            raise

        if self.cam.is_armed:
            self.cam.disarm()
        self.cam.image_poll_timeout_ms = 0

        self._abort_acquisition = False
        self.bulb_mode = False
        self.trigger_edge_type = 'rising'
        self._buffer_count = self.MIN_BUFFER_COUNT

        # The configuration that the camera is armed with, as returned by
        # _acquisition_config(), or None if the camera is not armed:
        self._armed_config = None
        # Time in seconds that grab() waits for a frame, computed when the camera is
        # armed:
        self._grab_timeout = None
        # The camera's count of the last frame retrieved since the camera was armed. The
        # camera counts frames from 1 after it is armed.
        self._last_frame_count = 0
        # Number of frames that were missing in grab_multiple(). The worker resets it
        # for each shot.
        self.n_dropped_frames = 0

        # Attribute values read from the camera, by name. Reading an attribute from the
        # SDK takes about 10 ms, and the values change only when we set them, so they
        # are cached until an attribute is set.
        self._attribute_cache = {}

        # The attributes that this model supports:
        self._attribute_names = []
        for names in VISIBILITY_LEVEL_ATTRIBUTES.values():
            for name in names:
                try:
                    self.get_attribute(name)
                except self._TLCameraError:
                    self.logger.debug('Attribute %s is not supported', name)
                else:
                    self._attribute_names.append(name)

        # The camera rounds the ROI to pixel multiples that depend on the binning, and
        # keeps the rounded ROI when the binning changes. We set the last requested ROI
        # again after setting the binning.
        self._requested_roi = self.get_attribute('roi')

    def set_attributes(self, attr_dict):
        for name, value in attr_dict.items():
            self.set_attribute(name, value)

    def set_attribute(self, name, value):
        if name not in self._attribute_names:
            raise ValueError(f"Unknown or unsupported attribute: {name}")
        with self._lock:
            if name in ENUM_ATTRIBUTES:
                enum = getattr(self._enums, ENUM_ATTRIBUTES[name])
                value = enum[value]
            else:
                # Convert to the type that the SDK returns, for example an exposure
                # time of 1e3 to the int 1000:
                value = type(self.get_attribute(name))(value)
            self._disarm()
            self._attribute_cache.clear()
            if name == 'bulb_mode':
                self.bulb_mode = value
            else:
                setattr(self.cam, name, value)
            if name == 'roi':
                self._requested_roi = value
            elif name in ('binx', 'biny'):
                self.cam.roi = self._requested_roi

    def get_attribute(self, name):
        with self._lock:
            if name not in self._attribute_cache:
                self._attribute_cache[name] = self._read_attribute(name)
            return self._attribute_cache[name]

    def _read_attribute(self, name):
        if name == 'bulb_mode':
            return self.bulb_mode
        value = getattr(self.cam, name)
        if name in ENUM_ATTRIBUTES:
            return value.name
        if name == 'roi':
            return tuple(value)
        return value

    def get_attribute_names(self, visibility_level):
        names = []
        for level, level_names in VISIBILITY_LEVEL_ATTRIBUTES.items():
            names.extend(name for name in level_names if name in self._attribute_names)
            if level == visibility_level.lower():
                break
        return names

    def _acquisition_config(self, continuous, hardware_triggered):
        return (
            continuous,
            hardware_triggered,
            self.bulb_mode,
            self.trigger_edge_type,
            self._buffer_count,
        )

    def _arm(self, continuous, hardware_triggered):
        config = self._acquisition_config(continuous, hardware_triggered)
        if config == self._armed_config:
            n_discarded = self._discard_pending_frames()
            self.logger.debug('Already armed, discarded %d stale frames', n_discarded)
            return
        self._disarm()
        modes = self._enums.OPERATION_MODE
        if not hardware_triggered:
            self.cam.operation_mode = modes.SOFTWARE_TRIGGERED
        elif self.bulb_mode:
            self.cam.operation_mode = modes.BULB
        else:
            self.cam.operation_mode = modes.HARDWARE_TRIGGERED
        polarities = self._enums.TRIGGER_POLARITY
        if self.trigger_edge_type == 'rising':
            self.cam.trigger_polarity = polarities.ACTIVE_HIGH
        else:
            self.cam.trigger_polarity = polarities.ACTIVE_LOW
        self.cam.frames_per_trigger_zero_for_unlimited = 0 if continuous else 1

        frame_interval = (
            1e-6 * self.get_attribute('exposure_time_us')
            + 1e-9 * self.cam.sensor_readout_time_ns
        )
        if 'is_frame_rate_control_enabled' in self._attribute_names:
            if self.get_attribute('is_frame_rate_control_enabled'):
                frame_rate = self.get_attribute('frame_rate_control_value')
                frame_interval = max(frame_interval, 1 / frame_rate)
        self._grab_timeout = frame_interval + self.GRAB_TIMEOUT_MARGIN

        t0 = perf_counter()
        self.cam.arm(self._buffer_count)
        self._armed_config = config
        self._last_frame_count = 0
        self.logger.debug(
            'Armed with %d buffers in %.1f ms',
            self._buffer_count,
            1000 * (perf_counter() - t0),
        )

    def _disarm(self):
        if self._armed_config is None:
            return
        t0 = perf_counter()
        self.cam.disarm()
        self._armed_config = None
        self.logger.debug('Disarmed in %.1f ms', 1000 * (perf_counter() - t0))

    def _get_pending_frame(self):
        """Return the next pending frame as an array, or None if there is none, and the
        number of frames that are missing before it. Updates self._last_frame_count."""
        frame = self.cam.get_pending_frame_or_null()
        if frame is None:
            return None, 0
        image = frame.image_buffer.copy()
        n_dropped = frame.frame_count - self._last_frame_count - 1
        self._last_frame_count = frame.frame_count
        return image, n_dropped

    def _discard_pending_frames(self):
        """Discard frames that the camera has already acquired. Returns the number of
        frames discarded."""
        n_discarded = 0
        while self._get_pending_frame()[0] is not None:
            n_discarded += 1
        return n_discarded

    def _wait_for_frame(self):
        """Wait for the next frame and return it as (image, n_dropped), where n_dropped
        is the number of missing frames before it. Raises TimeoutError if no frame
        arrives within self._grab_timeout."""
        deadline = perf_counter() + self._grab_timeout
        while True:
            with self._lock:
                image, n_dropped = self._get_pending_frame()
            if image is not None:
                return image, n_dropped
            if perf_counter() > deadline:
                raise TimeoutError("No frame acquired")
            time.sleep(self.GRAB_POLL_INTERVAL)

    def configure_acquisition(self, continuous=True, bufferCount=MIN_BUFFER_COUNT):
        with self._lock:
            self._buffer_count = max(self._buffer_count, bufferCount)
            self._arm(continuous=continuous, hardware_triggered=not continuous)
            if continuous:
                self.cam.issue_software_trigger()

    def snap(self):
        """Acquire a single software-triggered frame."""
        with self._lock:
            self._arm(continuous=False, hardware_triggered=False)
            self.cam.issue_software_trigger()
        try:
            image, _ = self._wait_for_frame()
        finally:
            with self._lock:
                self._disarm()
        return image

    def grab(self):
        """Wait for a frame of a continuous acquisition and return the most recent
        frame."""
        image, _ = self._wait_for_frame()
        with self._lock:
            while True:
                newer_image, _ = self._get_pending_frame()
                if newer_image is None:
                    return image
                image = newer_image

    def grab_multiple(self, n_images, images):
        """Append n_images frames of a hardware-triggered acquisition to images. Returns
        when they have been acquired, when abort_acquisition() is called, or when a
        frame is missing."""
        print(f"Attempting to grab {n_images} images.")
        for i in range(n_images):
            while True:
                if self._abort_acquisition:
                    print("Abort during acquisition.")
                    self._abort_acquisition = False
                    return
                with self._lock:
                    image, n_dropped = self._get_pending_frame()
                if image is not None:
                    break
                time.sleep(self.GRAB_POLL_INTERVAL)
            if n_dropped:
                self.n_dropped_frames = n_dropped
                msg = f"""The camera dropped {n_dropped} frame(s) before frame {i + 1}.
                    Saving the first {i} frames only."""
                print(' '.join(msg.split()), file=sys.stderr)
                return
            images.append(image)
            print(f"Got image {i + 1} of {n_images}.")
        print(f"Got {len(images)} of {n_images} images.")

    def stop_acquisition(self):
        with self._lock:
            if self._armed_config is not None and not self._armed_config[1]:
                # Software-triggered acquisition. A hardware-triggered acquisition
                # stays armed for the next shot.
                self._disarm()

    def abort_acquisition(self):
        self._abort_acquisition = True

    def close(self):
        with self._lock:
            if self.cam is not None:
                self._disarm()
                self.cam.dispose()
                self.cam = None
            if self.camera_lock is not None:
                self.camera_lock.release()
                self.camera_lock = None


class ThorlabsTSICameraWorker(IMAQdxCameraWorker):
    interface_class = ThorlabsTSICamera

    def get_camera(self):
        if self.mock:
            return super().get_camera()
        return self.interface_class(self.serial_number, self.logger)

    def transition_to_buffered(self, device_name, h5_filepath, initial_values, fresh):
        if getattr(self, 'is_remote', False):
            local_h5_filepath = path_to_local(h5_filepath)
        else:
            local_h5_filepath = h5_filepath
        with h5py.File(local_h5_filepath, 'r') as f:
            properties = labscript_utils.properties.get(
                f, self.device_name, 'device_properties'
            )
        self.camera.trigger_edge_type = properties['trigger_edge_type']
        self.camera.n_dropped_frames = 0
        return super().transition_to_buffered(
            device_name, h5_filepath, initial_values, fresh
        )

    def transition_to_manual(self):
        exception_on_failed_shot = self.exception_on_failed_shot
        result = super().transition_to_manual()
        n_dropped = getattr(self.camera, 'n_dropped_frames', 0)
        if n_dropped and exception_on_failed_shot:
            msg = f"The camera dropped {n_dropped} frame(s). The other images are saved."
            raise RuntimeError(msg)
        return result

    def shutdown(self):
        super().shutdown()
        _dispose_sdk()
