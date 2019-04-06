import nivision as nv
from blacs.tab_base_classes import Worker
import threading
import numpy as np
from labscript_utils.connections import ConnectionTable
import labscript_utils.properties
import labscript_utils.h5_lock
import h5py


class IMAQdx_Camera(object):
    def __init__(self, serial_number):
        # Find the camera:
        for cam in nv.IMAQdxEnumerateCameras(True):
            if serial_number == (cam.SerialNumberHi << 32) + cam.SerialNumberLo:
                self.camera = cam
                break
        else:
            msg = f"No connected camera with serial number {serial_number:X} found"
            raise Exception(msg)
        # Connect to the camera:
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
        nv.IMAQdxConfigureAcquisition(self.imaqdx, continuous=continuous,
                                      bufferCount=bufferCount)
        nv.IMAQdxStartAcquisition(self.imaqdx)

    def grab(self, waitForNextBuffer=True):
        nv.IMAQdxGrab(self.imaqdx, self.img, waitForNextBuffer=waitForNextBuffer)
        return self._decode_image_data(self.img)

    def grab_multiple(self, n_images, images, waitForNextBuffer=True):
        print(f"Attempting to grab {n_images} images.")
        for i in range(n_images):
            if self._abort_acquisition:
                print("Abort during acquisition.")
                self._abort_acquisition = False
                break
            try:
                images.append(self.grab(waitForNextBuffer))
                print(f"Got image {i} of {n_images}.")
            except nv.ImaqDxError as e:
                if e.code == nv.IMAQdxErrorTimeout.value:
                    print('.', end='')
                else:
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
        self.camera = IMAQdx_Camera(self.serial_number)
        self.camera.set_attributes(self.imaqdx_attributes)
        self.images = None
        self.n_images = None
        self.all_attributes = None
        self.exposures = None
        self.acquisition_thread = None
        self.h5_filepath = None

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
        attrs = repr(self.get_attributes_as_dict(visibility_level))
        # Format it nicely:
        attrs = attrs.replace('{', '{\n    ')
        attrs = attrs.replace(', ', ',\n    ')
        attrs = attrs.replace('}', ',\n}')
        return attrs

    def snap(self):
        """Acquire one frame in manual mode"""
        return self.camera.snap()

    def transition_to_buffered(self, device_name, h5_filepath, initial_values, fresh):
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
            # Get the stop_time from the device properties of the master pseudoclock.
            # This will be used to set the acquisition timeout if the user has not
            # specified it in the imaqdx_attributes dict.
            master_pseudoclock = ConnectionTable(h5_filepath).master_pseudoclock
            stop_time = labscript_utils.properties.get(
                f, master_pseudoclock, 'device_properties'
            )['stop_time']

        # We are pretty sure this attribute name is universal across all cameras.
        # We confirmed it exists across four different brands of scientific cameras.
        TIMEOUT_ATTRIBUTE = 'AcquisitionAttributes::Timeout'

        # Set the camera attributes.
        if TIMEOUT_ATTRIBUTE not in imaqdx_attributes:
            # Set acquisition timeout to fixed value, 5 seconds after the end of the
            # shot:
            print(f"Setting {TIMEOUT_ATTRIBUTE} to {stop_time + 5:.3f}s")
            self.camera.set_attribute(TIMEOUT_ATTRIBUTE, 1e3 * (stop_time + 5))
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
            print('No camera exposures in this shot.\n\n')
            return True
        assert self.acquisition_thread is not None
        self.acquisition_thread.join(timeout=5)
        if self.acquisition_thread.is_alive():
            print("Acquisition not finished before transition_to_static. Aborting.")
            return self.abort()
        self.acquisition_thread = None
        print(f"Saving {len(self.images)} images.'")

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
            for i, exposure in enumerate(self.exposures):
                group = image_group.require_group(exposure['name'])
                dset = group.create_dataset(
                    exposure['frametype'],
                    data=self.images[i],
                    dtype='uint16',
                    compression='gzip',
                )
                # Specify this dataset should be viewed as an image
                dset.attrs['CLASS'] = np.string_('IMAGE')
                dset.attrs['IMAGE_VERSION'] = np.string_('1.2')
                dset.attrs['IMAGE_SUBCLASS'] = np.string_('IMAGE_GRAYSCALE')
                dset.attrs['IMAGE_WHITE_IS_ZERO'] = np.uint8(0)
                print(f"Saved frame {exposure['frametype']}")

        print("Stopping IMAQdx acquisition.\n\n")
        self.camera.stop_acquisition()
        self.images = None
        self.n_images = None
        self.all_attributes = None
        self.exposures = None
        self.h5_filepath = None
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
        return True

    def abort_buffered(self):
        return self.abort()
        
    def abort_transition_to_buffered(self):
        return self.abort()
        
    def program_manual(self, values):
        return {}
    
    def shutdown(self):
        self.camera.close()

