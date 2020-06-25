#####################################################################
#                                                                   #
# /labscript_devices/imaqdx_server.py                               #
#                                                                   #
# Copyright 2018, Joint Quantum Institute                           #
#                                                                   #
# This file is part of labscript_utils, in the labscript suite      #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
import nivision as nv
import time
import numpy as np
import sys
from labscript_utils.camera_server import CameraServer
import labscript_utils.properties
import labscript_utils.shared_drive
# importing this wraps zlock calls around HDF file openings and closings:
import labscript_utils.h5_lock
import h5py
import threading

__author__ = ['dt', 'rpanderson', 'cbillington']

# NIVision contains IMAQdx functions
# <NI_install_path>\Vision\Documentation\NIVisionCVI.chm
# for help on these functions
# <NI_install_path>\NI-IMAQdx\Docs\NI-IMAQdx_Function_Reference.chm

# Monkeypatch the nivision library to fix a memory leak:
from labscript_devices.IMAQdxCamera.blacs_workers import _monkeypatch_imaqdispose
_monkeypatch_imaqdispose()

def _ensure_str(s):
    """Convert bytestrings and numpy strings to python strings.
    Leave other types unchanged.
    """
    if isinstance(s, bytes):
        return s.decode()
    elif isinstance(s, np.string_):
        return str(s)
    else:
        return s


def enumerate_cameras(connectedOnly=True):
    return nv.IMAQdxEnumerateCameras(connectedOnly)

class IMAQdx_Camera(object):
    def __init__(self, sn=None, alias=None):

        cams = enumerate_cameras()
        for cam in cams:
            if alias and not sn:
                if bytes(alias, encoding='ascii') == cam.InterfaceName:
                    self.camera = cam
                    print(f'Connected to {alias}.')
                    break
            elif sn and not alias:
                hi = cam.SerialNumberHi
                lo = cam.SerialNumberLo
                hb = hi.to_bytes(4, 'big')
                lb = lo.to_bytes(4, 'big')
                xx = int.from_bytes(hb+lb, 'big')
                if not xx == sn:
                    xx = hex(xx).split('x')[-1].upper()
                if isinstance(sn, str):
                    sn = sn.upper()
                if xx == sn:
                    self.camera = cam
                    print(f'Connected to {sn}.')
                    break
            else:
                raise Exception('Need to define either alias or sn to connect to camera.')


        try:
            print('Opening camera in controller mode.')
            print('self.camera.InterfaceName is', self.camera.InterfaceName)
            
            self.imaqdx = nv.IMAQdxOpenCamera(self.camera.InterfaceName,
                                              nv.IMAQdxCameraControlModeController)
        except AttributeError:
            print('Camera not found.')

        # Keep an img attribute so we don't have to create it every time
        print('Creating image object.')
        self.img = nv.imaqCreateImage(nv.IMAQ_IMAGE_U16)

        self._abort_acquisition = False

    def close(self):
        nv.IMAQdxCloseCamera(self.imaqdx)

    def enumerate_attributes(self, root='', writeable=True, visibility='simple'):
        # root can be AcquisitionAttributes, CameraAttributes,
        # CameraInformation and the like
        if visibility == 'simple':
            visibility = nv.IMAQdxAttributeVisibilitySimple
        elif visibility == 'intermediate':
            visibility = nv.IMAQdxAttributeVisibilityIntermediate
        elif visibility == 'advanced':
            visibility = nv.IMAQdxAttributeVisibilityAdvanced
        else:
            raise Exception("visibility can be 'simple', "
                            "'inetermediate' or 'advanced'.")

        attrs = nv.IMAQdxEnumerateAttributes2(self.imaqdx,
                                              bytes(root, encoding='utf8'),
                                              visibility)

        # returns an iterable conveniently
        if writeable:
            attrs_writeable = []
            for attr in attrs:
                if nv.IMAQdxIsAttributeWritable(self.imaqdx, attr.Name):
                    attrs_writeable.append(attr)

            return attrs_writeable  # this one return list

        return attrs # this one return ImaqArray

    def write_attribute_values_to_file(self, root='', writeable=True,
                                 visibility='simple'):
        attrs = self.enumerate_attributes(root, writeable, visibility)

        filename = self.camera.InterfaceName.decode('utf8') + '_attributes.txt'
        with open(filename, 'w') as f:
            for attr in attrs:
                attr_name = attr.Name.decode('utf8')
                value = self.get_attribute(attr_name)
                if value:
                    f.write(f"['{attr_name}', ")
                    f.write(f"'{value}'],\n")

            # delete that last comma
            f.seek(0,2)
            size = f.tell()
            f.truncate(size-3)

    def get_attribute(self, attr):
        try:
            attr = nv.IMAQdxGetAttribute(self.imaqdx,
                                         bytes(attr, encoding='utf8'))
        except nv.ImaqDxError as e:
            print('ImaqDxError: ' + str(e))
            return None

        # It can either be a number or IMAQdxEnumItem. Return value or name
        try:
            return attr.Name.decode('utf8')
        except AttributeError:
            return attr

    def get_attribute_options(self, attr):
        try:
            return nv.IMAQdxEnumerateAttributeValues(self.imaqdx,
                                                     bytes(attr, encoding='utf8'))
        except nv.ImaqDxError as e:
            print('ImaqDxError: ' + str(e))
            return None

    # class IMAQdxValueType(Enumeration): pass
    # IMAQdxValueTypeU32 = IMAQdxValueType(0)
    # IMAQdxValueTypeI64 = IMAQdxValueType(1)
    # IMAQdxValueTypeF64 = IMAQdxValueType(2)
    # IMAQdxValueTypeString = IMAQdxValueType(3)
    # IMAQdxValueTypeEnumItem = IMAQdxValueType(4)
    # IMAQdxValueTypeBool = IMAQdxValueType(5)
    # IMAQdxValueTypeDisposableString = IMAQdxValueType(6)

    def get_attribute_type(self, attr):
        # TODO wrap this up in above enum
        return nv.IMAQdxGetAttributeType(self.imaqdx,
                                         bytes(attr, encoding='utf8'))

    def print_attribute_description(self, attr):
        print(nv.IMAQdxGetAttributeDescription(self.imaqdx,
                                         bytes(attr, encoding='utf8')))

    def set_attribute(self, attr, value):
        # attr names need to be bytes but values can be strings
        attr = _ensure_str(attr).encode('utf8')
        assert isinstance(value, (bytes, str, float))
        nv.IMAQdxSetAttribute(self.imaqdx, attr, value)

    def set_attributes_dict(self, attr_dict):
        for k, v in attr_dict.items():
            self.set_attribute(k, v)

    def snap(self):
        # img = nv.imaqCreateImage(nv.IMAQ_IMAGE_U16)
        nv.IMAQdxSnap(self.imaqdx, self.img)

        return self._decode_image_data(self.img)

    def configure_acquisition(self, continuous=True, bufferCount=5):
        nv.IMAQdxConfigureAcquisition(self.imaqdx, continuous=continuous,
                                      bufferCount=bufferCount)
        nv.IMAQdxStartAcquisition(self.imaqdx)

    def stop_acquisition(self):
        nv.IMAQdxStopAcquisition(self.imaqdx)
        nv.IMAQdxUnconfigureAcquisition(self.imaqdx)

    def grab(self, waitForNextBuffer=True):
        nv.IMAQdxGrab(self.imaqdx, self.img,
                      waitForNextBuffer=waitForNextBuffer)

        return self._decode_image_data(self.img)

    def grab_multiple(self, n_images, imgs, waitForNextBuffer=True):
        print(f'Attempting to grab {n_images} images.')
        idx = 0
        while idx < n_images:
            if self._abort_acquisition:
                print('Abort during acquisition.')
                self._abort_acquisition = False
                break
            try:
                imgs.append(self.grab(waitForNextBuffer))
                idx += 1
                print(f'Got image {idx} of {n_images}.')
            except nv.ImaqDxError as e:
                if e.code == nv.IMAQdxErrorTimeout.value:
                    print('.', end='')
            except Exception:
                raise

        print(f'Got {len(imgs)} of {n_images} images.')


    def abort_acquisition(self):
        self._abort_acquisition = True


    def _decode_image_data(self, img):
        img_array = nv.imaqImageToArray(img)
        img_array_shape = (img_array[2], img_array[1])

        # bitdepth in bytes
        bitdepth = len(img_array[0]) // (img_array[1] * img_array[2])
        # print(bitdepth)
        if bitdepth == 1:
            dtype = np.uint8
        elif bitdepth == 2:
            dtype = np.uint16
        elif bitdepth == 4:
            dtype = np.uint32
        else:
            raise ValueError(dtype)

        data = np.frombuffer(img_array[0], dtype=dtype).reshape(img_array_shape)

        return data.copy()


class IMAQdxCameraServer(CameraServer):
    """Subclass of CameraServer for IMAQdx cameras."""

    def __init__(self, port, camera, camera_name, 
                 image_path='images/', named_exposures=True, imageify=True):
        CameraServer.__init__(self, port)
        self.camera = camera
        self.camera_name = camera_name
        self.image_path = image_path
        self.named_exposures = named_exposures
        self.imageify = imageify
        self.imgs = []
        self.acquisition_thread = None
        self.n_images = 0


    def transition_to_buffered(self, h5_filepath):
        # Parse the h5 file for number of exposures and camera properties
        with h5py.File(h5_filepath, 'r') as h5_file:
            group = h5_file['devices'][self.camera_name]
            if not 'EXPOSURES' in group:
                print('No camera exposures in this shot.')
                self.n_images = 0
                return
            self.exposures = group['EXPOSURES'].value
            self.n_images = len(group['EXPOSURES'])

            # Get the imaqdx_properties from the device_properties
            self.device_properties = labscript_utils.properties.get(
                h5_file, self.camera_name, 'device_properties')
            imaqdx_properties = self.device_properties['added_properties']

            # Get the exposure time
            exposure_time = self.device_properties['exposure_time']

            # Get the stop time of the experiment
            devices = [self.camera_name.encode()]
            connection_table = h5_file['/connection table'].value
            try:
                while not devices[-1] == b'None' and len(devices) < len(connection_table):
                    parent_device = connection_table[connection_table['name'] == devices[-1]]['parent'][0]
                    devices.append(parent_device)
                parent_device = devices[-2]
                stop_time = h5_file[b'/devices/' + parent_device].attrs['stop_time']
            except KeyError:
                print('Could not determine experiment shot duration.')
                stop_time = None

        # Set the camera properties
        timeout_attr = 'AcquisitionAttributes::Timeout'
        exposure_attr = 'CameraAttributes::Controls::Exposure::ExposureTimeAbs'
        if timeout_attr not in imaqdx_properties:
            # Set acquisition timeout to fixed value
            print('Setting {} to {:.3f}s'.format(timeout_attr, stop_time + 5))
            self.camera.set_attribute(timeout_attr, 1e3 * (stop_time + 5))
        if exposure_attr not in imaqdx_properties and exposure_time is not None:
            print('Setting {} to {:.3f}ms'.format(exposure_attr, 1e3 * exposure_time))
            self.camera.set_attribute(exposure_attr, 1e6 * exposure_time)
        if len(imaqdx_properties):
            print('Updating the following IMAQdx properties:')
            for key, val in imaqdx_properties.items():
                print('{:}: {:}'.format(key, val))
            print('\n')
            self.camera.set_attributes_dict(imaqdx_properties)

        # Get the camera properties
        self.exposure_time = self.camera.get_attribute(exposure_attr)
        self.width = self.camera.get_attribute('CameraAttributes::ImageFormat::Width')
        self.height = self.camera.get_attribute('CameraAttributes::ImageFormat::Height')
        self.binning_horizontal = self.camera.get_attribute('CameraAttributes::ImageMode::BinningHorizontal')
        self.binning_vertical = self.camera.get_attribute('CameraAttributes::ImageMode::BinningVertical')
        self.pixel_format = self.camera.get_attribute('CameraAttributes::ImageFormat::PixelFormat')


        print(f'Configuring camera for {self.n_images} images.')
        self.camera.configure_acquisition(continuous=False, bufferCount=self.n_images)
        self.imgs.clear()
        self.acquisition_thread = threading.Thread(target=self.camera.grab_multiple,
                                                   args=(self.n_images, self.imgs),
                                                   daemon=True)
        self.acquisition_thread.start()


    def transition_to_static(self, h5_filepath):

        start_time = time.time()
        if self.n_images:
            assert self.acquisition_thread is not None, 'transition_to_static called without acquisition thread'
            self.acquisition_thread.join(timeout=1)
            if self.acquisition_thread.is_alive():
                print('Acquisition not finished before transition_to_static. Aborting.')
                self.imgs.clear()
                self.abort()
                return
            self.acquisition_thread = None
            print(f'Saving {len(self.imgs)} images.')

            # if len(self.imgs) != n_images:
            #     try:
            #         raise RuntimeError(f"Number of images {len(self.imgs)} "
            #                            f"not equal to expected {n_images}")
            #     except RuntimeError:
            #         zprocess.raise_exception_in_thread(sys.exc_info())
            #     # Just save the first however many we were expecting:
            #     self.imgs = self.imgs[:n_images]

            with h5py.File(h5_filepath, 'r+') as h5_file:
                # Use orientation for image path, camera_name if orientation unspecified
                if self.device_properties['orientation']:
                    image_path = self.image_path + _ensure_str(self.device_properties['orientation'])
                else:
                    image_path = self.image_path + _ensure_str(self.camera_name)
                image_group = h5_file.require_group(image_path)
                image_group.attrs['camera'] = self.camera_name.encode('utf8')
                image_group.attrs.create(
                    'ExposureTimeAbs', self.exposure_time, dtype='float64')
                image_group.attrs.create(
                    'Width', self.width, dtype='int64')
                image_group.attrs.create(
                    'Height', self.height, dtype='int64')
                if self.binning_horizontal:
                    image_group.attrs.create(
                        'BinningHorizontal', self.binning_horizontal, dtype='int8')
                if self.binning_vertical:
                    image_group.attrs.create(
                        'BinningVertical', self.binning_vertical, dtype='int8')
                if self.named_exposures:
                    for i, exposure in enumerate(self.exposures):
                        group = image_group.require_group(exposure['name'])
                        dset = group.create_dataset(exposure['frametype'], data=self.imgs[i],
                                                    dtype='uint16', compression='gzip')
                        if self.imageify:
                            # Specify this dataset should be viewed as an image
                            dset.attrs['CLASS'] = np.string_('IMAGE')
                            dset.attrs['IMAGE_VERSION'] = np.string_('1.2')
                            dset.attrs['IMAGE_SUBCLASS'] = np.string_(
                                'IMAGE_GRAYSCALE')
                            dset.attrs['IMAGE_WHITE_IS_ZERO'] = np.uint8(0)
                        print('Saved frame {:}'.format(exposure['frametype']))
                else:
                    image_group.create_dataset('Raw', data=np.array(self.imgs))
        else:
            print('No camera exposures in this shot.\n\n')
            return
        print(self.camera_name + ' saving time: {:.3f}ms'.format(1e3*(time.time()-start_time)))
        print('Stopping IMAQdx acquisition.\n\n')
        self.camera.stop_acquisition()


    def abort(self):
        if self.acquisition_thread is not None:
            self.camera.abort_acquisition()
            self.acquisition_thread.join()
            self.acquisition_thread = None
            self.camera.stop_acquisition()
        self.camera._abort_acquisition = False


if __name__ == '__main__':

    import sys
    try:
        camera_name = sys.argv[1]
    except IndexError:
        print('Call me with the name of a camera as defined in BLACS.')
        sys.exit(0)

    from labscript_utils.labconfig import LabConfig
    print('Reading labconfig')
    lc = LabConfig()

    h5_filepath = lc.get('paths', 'connection_table_h5')
    print(f'Getting properties of {camera_name} from connection table: {h5_filepath}')
    with h5py.File(h5_filepath, 'r') as h5_file:
        device_properties = labscript_utils.properties.get(
            h5_file, camera_name, 'device_properties')
        port = labscript_utils.properties.get(
            h5_file, camera_name, 'connection_table_properties')['BIAS_port']

    print('Getting imaqdx_properties from device_properties:')
    imaqdx_properties = device_properties['added_properties']
    # print(imaqdx_properties)

    # Get server settings
    server_kwargs = {}
    for option in ['image_path', 'named_exposures', 'imageify']:
        if lc.get('imaqdx_server', option, fallback=None):
            if option is 'image_path':
                val = lc.get('imaqdx_server', option)
            else:
                val = lc.getboolean('imaqdx_server', option)
            server_kwargs[option] = val
            print(f'Overriding {option} with {val}.')

    # Get the serial number
    serial_number = _ensure_str(device_properties['serial_number'])
    print(f'Instantiating IMAQdx_Camera (SN = {serial_number}).')
    camera = IMAQdx_Camera(sn=serial_number)
    if len(imaqdx_properties):
        print('Setting IMAQdx properties:')
        for key, val in imaqdx_properties.items():
            print('{:}: {:}'.format(key, val))
        print('\n')
        camera.set_attributes_dict(imaqdx_properties)

    print(f'Starting camera server on port {port}...')
    server = IMAQdxCameraServer(port, camera, camera_name, **server_kwargs)
    server.shutdown_on_interrupt()
    camera.close()
