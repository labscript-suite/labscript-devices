# import nivision as nv
from blacs.tab_base_classes import Worker
import numpy as np
from enum import Enum


# class AttrType(Enum):
#     IMAQdxValueTypeU32 = nv.IMAQdxValueType(0)
#     IMAQdxValueTypeI64 = nv.IMAQdxValueType(1)
#     IMAQdxValueTypeF64 = nv.IMAQdxValueType(2)
#     IMAQdxValueTypeString = nv.IMAQdxValueType(3)
#     IMAQdxValueTypeEnumItem = nv.IMAQdxValueType(4)
#     IMAQdxValueTypeBool = nv.IMAQdxValueType(5)
#     IMAQdxValueTypeDisposableString = nv.IMAQdxValueType(6)


class IMAQdx_Camera(object):
    def __init__(self, serial_number):
        # Find the camera:
        for cam in nv.IMAQdxEnumerateCameras(True):
            if serial_number == (cam.SerialNumberHi << 32) + cam.SerialNumberLo:
                self.camera = cam
                break
        else:
            msg = "No connected camera with serial number {:X} found"
            raise Exception(msg.format(serial_number))
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
        nv.IMAQdxSetAttribute(self.imaqdx, name.encode('utf8'), value)

    def get_attribute_names(self, visibility_level, writeable_only=True):
        """Return a list of all attribute names for the given visibility level, or
        optionally, only writeable attributes"""
        visibilities = {
            'simple': nv.IMAQdxAttributeVisibilitySimple,
            'intermediate': nv.IMAQdxAttributeVisibilityIntermediate,
            'advanced': nv.IMAQdxAttributeVisibilityAdvanced,
        }
        visibility_level = visibilities[visibility_level]
        attributes = []
        for a in nv.IMAQdxEnumerateAttributes2(self.imaqdx, b'', visibility_level):
            if writeable_only and not nv.IMAQdxIsAttributeWritable(self.imaqdx, a.Name):
                continue
            attributes.append(a.Name.decode('utf8'))
        return sorted(attributes)
    
    def get_attribute(self, name):
        """Return current value of attribute of the given name"""
        return nv.IMAQdxGetAttribute(self.imaqdx, name.encode('utf8'))

    def get_attribute_options(self, name):
        """Get possible values for attributes of IMAQdxValueTypeEnumItem type"""
        return nv.IMAQdxEnumerateAttributeValues(self.imaqdx, name.encode('utf8'))

    def get_attribute_dtype(self, name):
        """Return dtype associated with an attribute, as a AttrType enum"""
        return AttrType(nv.IMAQdxGetAttributeType(self.imaqdx, name.encode('utf8')))

    def get_attribute_description(self, name):
        """Return a string description of the attribute of the given name"""
        print(nv.IMAQdxGetAttributeDescription(self.imaqdx, name.encode('utf8')))

    def snap(self):
        """Acquire a single image and return it"""
        nv.IMAQdxSnap(self.imaqdx, self.img)
        return self._decode_image_data(self.img)

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
        return
        self.camera = IMAQdx_Camera(self.serial_number)
        self.camera.set_attributes(self.imaqdx_attributes)

    def get_attributes_as_text(self, visibility_level, include_comments):
        print("getting attributes at text")
        return "TODO: attributes here: {} {}".format(visibility_level, include_comments)

    def snap(self):
        """Acquire one frame in manual mode"""
        # TODO: actually get a frame
        return np.random.randint(0, 100, (1024, 1024), np.uint16)

    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):
        # h5file = shared_drive.path_to_agnostic(h5file)
        pass
        
    def transition_to_manual(self):
        pass

    def abort(self):
        pass

    def abort_buffered(self):
        return self.abort()
        
    def abort_transition_to_buffered(self):
        return self.abort()
        
    def program_manual(self, values):
        return {}
    
    def shutdown(self):
        return

