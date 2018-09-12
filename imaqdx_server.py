#####################################################################
#                                                                   #
# /labscript_utils/imaqdx_server.py                                 #
#                                                                   #
# Copyright 2017, Joint Quantum Institute                           #
#                                                                   #
# This file is part of labscript_utils, in the labscript suite      #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from __future__ import division, unicode_literals, print_function, absolute_import
from labscript_utils import PY2
if PY2:
    str = unicode

import nivision as nv
import time
import numpy as np
import os
import sys
import time
import zprocess
from labscript_utils import check_version
import labscript_utils.shared_drive
# importing this wraps zlock calls around HDF file openings and closings:
import labscript_utils.h5_lock
import h5py
check_version('zprocess', '1.3.3', '3.0')
import threading

__author__ = 'dt'

# for help on these functions
# IMAQdx
# <NI_install_path>\NI-IMAQdx\Docs\NI-IMAQdx_Function_Reference.chm

# NIVision contains imaq functions of which I need only imaqCreateImage()
# and imaqImageToArray()
# <NI_install_path>\Vision\Documentation\NIVisionCVI.chm


def _ensure_str(s):
    """convert bytestrings and numpy strings to python strings"""
    return s.decode() if isinstance(s, bytes) else str(s)


class IMAQdx_Camera():

    def enumerate_cameras(connectedOnly=True):
        return nv.IMAQdxEnumerateCameras(connectedOnly)

    def __init__(self, sn=None, alias=None):

        # TODO change init to serial number

        cams = IMAQdx_Camera.enumerate_cameras()
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
                xx = hex(xx).split('x')[-1].upper()

                if xx == sn:
                    self.camera = cam
                    print(f'Connected to {sn}.')
                    break
            else:
                raise Exception('Need to define either alias or sn to connect to camera.')
                    
                    
            # dir(cam) for attributes

        # Open it in controller mode
        try:
            print('Opening camera in controller mode.')
            print('self.camera.InterfaceName is', self.camera.InterfaceName)
            
            self.imaqdx = nv.IMAQdxOpenCamera(self.camera.InterfaceName,
                                              nv.IMAQdxCameraControlModeController)
        except AttributeError:
            print('Camera not found.')

        # keep an img object so I don't have to create it every time
        print('Creating image object.')
        self.img = nv.imaqCreateImage(nv.IMAQ_IMAGE_U16)

        self._abort_acquisition = False

    def close(self):
        # if self.acquisition_running:
        #     self.acquisition_stopping = True
        #     self.acquisition_thread.join()
        nv.IMAQdxCloseCamera(self.imaqdx)

    def enumerate_attributes(self, root='', writeable=True, visibility='simple'):
        # root can be AcquisitionAttributes, CameraAttributes,
        # CameraInformation and the like

        # TODO only encode if it's string. If it's bytes just pass it

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
        except TypeError:
            print('Cannot get attribute of type '
                  'IMAQdxAttributeTypeCommand = IMAQdxAttributeType(6).')
            return None

        # it can either be a number or IMAQdxEnumItem. Return value or name
        try:
            return attr.Name.decode('utf8')
        except AttributeError:
            return attr

    def get_attribute_options(self, attr):

        try:
            return nv.IMAQdxEnumerateAttributeValues(self.imaqdx,
                                                     bytes(attr, encoding='utf8'))
        except ImaqDxError:
            print('Attribute is not enum.')
            # not sure this is the only case here.

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
        assert isinstance(value, (bytes, str))
        nv.IMAQdxSetAttribute(self.imaqdx, attr, value)

    def set_attributes_dict(self, attr_dict):
        for k, v in attr_dict.items():
            self.set_attribute(k, v)

    def snap(self):
        # img = nv.imaqCreateImage(nv.IMAQ_IMAGE_U16)
        nv.IMAQdxSnap(self.imaqdx, self.img)

        return self._decode_image_data(self.img)

    def configure_aqquisition(self, continuous=True, bufferCount=5):

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
        idx = 0
        # for _ in range(n_images):
        while idx < n_images:
            if self._abort_acquisition:
                self._abort_acquisition = False
                break
            try:
                imgs.append(self.grab(waitForNextBuffer))
                # print('Got an image.')
                idx += 1
            except nv.ImaqDxError as e:
                if e.code == nv.IMAQdxErrorTimeout.value:
                    # print('Acquisition timeout.')
                    print('.', end='')
            except Exception:
                raise

        print(f'got {len(imgs)} images.')


    def abort_acquisition(self):
        self._abort_acquisition = True

    # def sequence(self, num_of_images):
    #     # Don't use this function
    #     raise Exception("Don't use this function.")
    #
    #     img_list = []
    #
    #     for _ in range(num_of_images):
    #         img_list.append(nv.imaqCreateImage(nv.IMAQ_IMAGE_U16))
    #
    #     imgs = nv.iterableToArray(img_list, type=nv.Image)
    #     nv.IMAQdxSequence(self.imaqdx, imgs[0])
    #
    #     # TODO this fails. Pointer in ImaqArray created above seems to
    #     # be pointing to nothing?
    #     # for idx in range(num_of_images):
    #     #     img_list[idx] = self._decode_image_data(imgs[0][idx])
    #
    #     return imgs

    def _decode_image_data(self, img):

        img_array = nv.imaqImageToArray(img)
        img_array_shape = (img_array[2], img_array[1])

        # bitdepth in bytes
        bitdepth = len(img_array[0]) // (img_array[1] * img_array[2])
        print(bitdepth)
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

    # TODO use
    # nv.IMAQdxReadAttributes()
    # nv.IMAQdxWriteAttributes()
    # to write attrs NOT to default file. Then I can compare with h5_properties
    # and only set the ones tha are different.


class IMAQdxCameraServer(CameraServer):
    """Minimalistic camera server. Transition to buffered and abort are not
    implemented, because we don't need to do anything in those cases. This
    camera server simply writes to the h5 file the images, which have been
    saved to disk during each shot by an external program."""
    def __init__(self, port, camera, camera_name):
        CameraServer.__init__(self, port)
        self.camera = camera
        self.camera_name = camera_name
        self.imgs = []

    def __init__(self, *args, **kwargs):
        CameraServer.__init__(self, *args, **kwargs)
        self.acquisition_thread = None

    def transition_to_buffered(self, h5_filepath):
        self.n_images = 0
        # How many images to get
        with h5py.File(h5_filepath, 'r') as f:
            # groupname = self.camera_name
            group = f['devices'][self.camera_name]
            if not 'EXPOSURES' in group:
                print('no camera exposures in this shot.')
                return
            self.n_images = len(group['EXPOSURES'])

            # This should be empty if the experiment doesn't define any
            # new properties
            imaqdx_properties = group.attrs['added_properties']
            if len(imaqdx_properties):
                print('Overwriting connection table attributes.')
                cam.set_attributes_dict(dict(imaqdx_properties))

        print(f'Configured for {self.n_images} images.')

        self.camera.configure_aqquisition()

        self.imgs = []
        self.acquisition_thread = threading.Thread(target=self.camera.grab_multiple,
                                                   args=(self.n_images, self.imgs),
                                                   daemon=True)
        self.acquisition_thread.start()


    def transition_to_static(self, h5_filepath):

        start_time = time.time()
        # with h5py.File(h5_filepath) as f:
        #     # for dev in f['devices']:
        #     #     attrs = dict(f['devices'][dev].attrs)
        #     #     if 'visa_resource' in attrs.keys():
        #     #         if self.scope.visa.resource_name == attrs['visa_resource']:
        #     #             groupname = dev
        #
        #     groupname = self.camera_name
        #     # print(groupname)
        #
        #     group = f['devices'][groupname]
        #     if not 'EXPOSURES' in group:
        #         print('no camera exposures in this shot.')
        #         return

        # print(self.group)

        if self.n_images:
        #         print('no camera exposures in this shot.')
        #         return

            # n_images = len(self.group['EXPOSURES'])

            self.acquisition_thread.join(timeout=1)
            if self.acquisition_thread.is_alive():
                print('Timeout in acquisition thread. Returning empty images.')
                self.imgs = []
                # zprocess.raise_exception_in_thread(sys.exc_info())
                               # for _ in range(n_images):
                #     self.imgs.append(np.zeros((500, 500)))
                self.camera.abort_acquisition()
            self.acquisition_thread.join()
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

            with h5py.File(h5_filepath) as f:
                group = f.create_group('/data/images' + self.camera_name)
                group.create_dataset('Raw',data=np.array(self.imgs))
        print(self.camera_name + ' camera shots saving time: %s s' %str(time.time() - start_time))

        self.camera.stop_acquisition()
        # print('to static out')

    def abort(self):
        if self.acquisition_thread is not None:
            self.camera.abort_acquisition()
            self.acquisition_thread.join()
            self.acquisition_thread = None
            self.camera.stop_acquisition()


if __name__ == '__main__':

    from labscript_utils.labconfig import LabConfig
    import labscript_utils.properties
    import h5py
    print('Reading labconfig')
    lc = LabConfig()

    import sys
    try:
        camera_name = sys.argv[1]
    except IndexError:
        print('Call me with the name of a camera as defined in BLACS.')
        sys.exit(0)

    h5_filepath = lc.get('paths', 'connection_table_h5')
    print('Getting properties of {:} from connection table: {:}'.format(camera_name, h5_filepath))
    with h5py.File(h5_filepath, 'r') as f:
        h5_attrs = labscript_utils.properties.get(f, camera_name,
                                                   'device_properties')
        blacs_port = labscript_utils.properties.get(f, camera_name,
                                    'connection_table_properties')['BIAS_port']


    # get the properties in a dict
    print('Converting camera properties to dictionary.')
    imaqdx_properties = dict(h5_attrs['added_properties'])
    # imaqdx_properties = dict(imaqdx_array)

    sn = _ensure_str(h5_attrs['serial_number'])
    # print(imaqdx_properties)

    print('Instantiating IMAQdx_Camera.')
    # cam = IMAQdx_Camera(alias=camera_name)
    cam = IMAQdx_Camera(sn=sn)
    # cam.write_attribute_values_to_file()
    print('Setting camera attributes.')
    cam.set_attributes_dict(imaqdx_properties)
    # Get the attributes from the shared connection table.
    # Then overwrite them per experiment if the experiment defines any new ones


    print('starting camera server on port %d...' % blacs_port)
    server = IMAQdxCameraServer(blacs_port, cam, camera_name)
    server.shutdown_on_interrupt()
    cam.close()
