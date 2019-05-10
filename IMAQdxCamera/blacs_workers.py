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

# Required for knowing the parent device's hostname when running remotely:
from labscript_utils import check_version

check_version('zprocess', '2.12.0', '3')

# Don't import nv yet so as not to throw an error,
# allow worker to run as a dummy device
nv = None

class MockCamera(object):
    """Mock camera class that returns fake image data."""

    def __init__(self):
        self.attributes = {}

    def set_attributes(self, attributes):
        self.attributes.update(attributes)

    def get_attribute(self, name):
        return self.attributes[name]

    def get_attribute_names(self, visibility_level=None):
        return list(self.attributes.keys())

    def configure_acquisition(self, continuous=False, bufferCount=5):
        pass

    def grab(self):
        return self.snap()

    def grab_multiple(self, n_images, images, waitForNextBuffer=True):
        print(f"Attempting to grab {n_images} (mock) images.")
        for i in range(n_images):
            images.append(self.grab())
            print(f"Got (mock) image {i+1} of {n_images}.")
        print(f"Got {len(images)} of {n_images} (mock) images.")

    def snap(self):
        N = 500
        A = 500
        x = np.linspace(-5, 5, 500)
        y = x.reshape((N, 1))
        clean_image = A * (1 - 0.5 * np.exp(-(x ** 2 + y ** 2)))

        # Write text on the image that says "NOT REAL DATA"
        from PIL import Image, ImageDraw, ImageFont

        font = ImageFont.load_default()
        canvas = Image.new('L', [N // 5, N // 5], (0,))
        draw = ImageDraw.Draw(canvas)
        draw.text((10, 20), "NOT REAL DATA", font=font, fill=1)
        clean_image += 0.2 * A * np.asarray(canvas.resize((N, N)).rotate(20))
        return np.random.poisson(clean_image)

    def stop_acquisition(self):
        pass

    def abort_acquisition(self):
        pass

    def close(self):
        pass


class IMAQdx_Camera(object):
    def __init__(self, serial_number):
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
        self._abort_acquisition = False

    def set_attributes(self, attr_dict):
        for k, v in attr_dict.items():
            self.set_attribute(k, v)

    def set_attribute(self, name, value):
        """Set the value of the attribute of the given name to the given value"""
        if isinstance(value, str):
            value = value.encode('utf8')
        try:
            nv.IMAQdxSetAttribute(self.imaqdx, name.encode('utf8'), value)
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
        return sorted(attributes)

    def get_attribute(self, name):
        """Return current value of attribute of the given name"""
        try:
            return nv.IMAQdxGetAttribute(self.imaqdx, name.encode('utf8'))
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
                except nv.ImaqDxError as e:
                    if e.code == nv.IMAQdxErrorTimeout.value:
                        print('.', end='')
                        continue
                    raise
        print(f"Got {len(images)} of {n_images} images.")

    def stop_acquisition(self):
        nv.IMAQdxStopAcquisition(self.imaqdx)
        nv.IMAQdxUnconfigureAcquisition(self.imaqdx)

    def abort_acquisition(self):
        self._abort_acquisition = True

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


class IMAQdxCameraWorker(Worker):
    def init(self):
        if self.mock:
            print("Starting device worker as a mock device")
            self.camera = MockCamera()
        else:
            global nv
            import nivision as nv
            self.camera = IMAQdx_Camera(self.serial_number)
        print("Setting attributes...")
        self.camera.set_attributes(self.imaqdx_attributes)
        self.camera.set_attributes(self.manual_mode_imaqdx_attributes)
        print("Initialisation complete")
        self.images = None
        self.n_images = None
        self.all_attributes = None
        self.exposures = None
        self.acquisition_thread = None
        self.h5_filepath = None
        self.continuous_stop = threading.Event()
        self.continuous_thread = None
        self.continuous_dt = None
        self.image_socket = Context().socket(zmq.REQ)
        self.image_socket.connect(
            f'tcp://{self.parent_host}:{self.image_receiver_port}'
        )

    def get_attributes_as_dict(self, visibility_level):
        """Return a dict of the attributes of the camera for the given visibility
        level"""
        names = self.camera.get_attribute_names(visibility_level)
        attributes_dict = {}
        for name in names:
            value = self.camera.get_attribute(name)
            if isinstance(value, nv.core.IMAQdxEnumItem):
                value = value.Name
            if isinstance(value, bytes):
                value = value.decode('utf8')
            attributes_dict[name] = value
        return attributes_dict

    def get_attributes_as_text(self, visibility_level):
        """Return a string representation of the attributes of the camera for
        the given visibility level"""
        attrs = self.get_attributes_as_dict(visibility_level)
        # Format it nicely:
        lines = [f'    {repr(key)}: {repr(value)},' for key, value in attrs.items()]
        dict_repr = '\n'.join(['{'] + lines + ['}'])
        return self.device_name + '_imaqdx_attributes = ' + dict_repr

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

            # Get the imaqdx_attributes from the device_properties
            device_properties = labscript_utils.properties.get(
                f, self.device_name, 'device_properties'
            )
            imaqdx_attributes = device_properties['imaqdx_attributes']
        self.camera.set_attributes(imaqdx_attributes)
        # Get the camera attributes, so that we can save them to the H5 file:
        self.all_attributes = self.get_attributes_as_dict(visibility_level='advanced')

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
        self.acquisition_thread.join(timeout=5)
        if self.acquisition_thread.is_alive():
            self.abort()
            msg = """Acquisition thread did not finish. Likely did not acquire
                expected number of images. Check triggering is
                connected/configured correctly"""
            raise RuntimeError(dedent(msg))
        self.acquisition_thread = None
        print(f"Saving {len(self.images)} images.")

        with h5py.File(self.h5_filepath) as f:
            # Use orientation for image path, device_name if orientation unspecified
            if self.orientation is not None:
                image_path = 'images/' + self.orientation
            else:
                image_path = 'images/' + self.device_name
            image_group = f.require_group(image_path)
            image_group.attrs['camera'] = self.device_name

            # Save all imaqdx attributes to the HDF5 file:
            image_group.attrs.update(self.all_attributes)

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
                dset.attrs['CLASS'] = np.string_('IMAGE')
                dset.attrs['IMAGE_VERSION'] = np.string_('1.2')
                dset.attrs['IMAGE_SUBCLASS'] = np.string_('IMAGE_GRAYSCALE')
                dset.attrs['IMAGE_WHITE_IS_ZERO'] = np.uint8(0)

        print("Stopping IMAQdx acquisition.")
        self.camera.stop_acquisition()
        self.images = None
        self.n_images = None
        self.all_attributes = None
        self.exposures = None
        self.h5_filepath = None
        print("Setting manual mode attributes.\n")
        self.camera.set_attributes(self.manual_mode_imaqdx_attributes)
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
        self.all_attributes = None
        self.exposures = None
        self.acquisition_thread = None
        self.h5_filepath = None
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
