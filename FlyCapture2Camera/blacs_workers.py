#####################################################################
#                                                                   #
# /labscript_devices/FlyCapture2Camera/blacs_workers.py             #
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
# Original PyCapture2_camera_server by dsbarker
# Ported to BLACS worker by dihm

import numpy as np
from labscript_utils import dedent
from enum import IntEnum

from labscript_devices.IMAQdxCamera.blacs_workers import IMAQdxCameraWorker

# Don't import API yet so as not to throw an error, allow worker to run as a dummy
# device, or for subclasses to import this module to inherit classes without requiring API
PyCapture2 = None

class FlyCapture2_Camera(object):
    def __init__(self, serial_number):
        """Initialize FlyCapture2 API camera.
        
        Serial number should be of int type."""
        
        global PyCapture2
        import PyCapture2
        
        ver = PyCapture2.getLibraryVersion()
        min_ver = (2,12,3,31) # first release with python 3.6 support
        if ver < min_ver:
            raise RuntimeError(f"PyCapture2 version {ver} must be >= {min_ver}")
        
        bus = PyCapture2.BusManager()
        self.camera = PyCapture2.Camera()
        self.camera.connect(bus.getCameraFromSerialNumber(serial_number))
        
        config = self.camera.getConfiguration()
        config.grabTimeout = 1000 # in ms
        config.highPerformanceRetrieveBuffer = True
        self.camera.setConfiguration(config)
        # set which values of properties to return
        self.get_props = ['present','absControl','absValue',
                          'onOff','autoManualMode',
                          'valueA','valueB']
        
        fmts = {prop:getattr(PyCapture2.PIXEL_FORMAT,prop) 
                for prop in dir(PyCapture2.PIXEL_FORMAT) 
                if not prop.startswith('_')}
                
        self.pixel_formats = IntEnum('pixel_formats',fmts)

        self._abort_acquisition = False

    def set_attributes(self, attr_dict):
        """Sets all attribues in attr_dict.
        FlyCapture does not control all settings through same interface,
        so we must do them separately.
        Interfaces are: {
            <Standard PROPERTY_TYPE>,
            'TriggerMode',
            'ImageMode'}
        """
        
        for prop, vals in attr_dict.items():
            if prop == 'TriggerMode':
                self.set_trigger_mode(vals)
                
            elif prop == 'ImageMode':
                self.set_image_mode(vals)
                
            else:
                self.set_attribute(prop, vals)
                
    def set_trigger_mode(self,trig_dict):
        """Configures triggering options via Trigger Mode interface."""
        trig_mode = self.camera.getTriggerMode()
        for k,v in trig_dict.items():
            setattr(trig_mode,k,v)
        
        try:
            self.camera.setTriggerMode(trig_mode)
        except Exception as e:
            msg = "Failed to set Trigger Mode!"
            raise Exception(msg) from e
            
    def set_image_mode(self,image_settings):
        """Configures ROI and image control via Format 7, Mode 0 interface."""
        image_info, supported = self.camera.getFormat7Info(0)
        Hstep = image_info.offsetHStepSize
        Vstep = image_info.offsetVStepSize
        image_dict = image_settings.copy()
        if supported:
            image_mode, packetSize, percentage = self.camera.getFormat7Configuration()
            image_mode.mode = 0
            
            # validate and set the ROI settings
            # this rounds the ROI settings to nearest allowed pixel            
            if 'offsetX' in image_dict:
                image_dict['offsetX'] -= image_dict['offsetX'] % Hstep
            if 'offsetY' in image_dict:
                image_dict['offsetY'] -= image_dict['offsetY'] % Vstep
            if 'width' in image_dict:
                image_dict['width'] -= image_dict['width'] % Hstep
            if 'height' in image_dict:
                image_dict['height'] -= image_dict['height'] % Vstep

            # need to set pixel format separately to get correct enum value
            if 'pixelFormat' in image_dict:
                fmt = image_dict.pop('pixelFormat')
                image_mode.pixelFormat = self.pixel_formats[fmt].value
                
            for k,v in image_dict.items():
                setattr(image_mode,k,v)
                
            try:            
                fmt7PktInfo, valid = self.camera.validateFormat7Settings(image_mode)
                if valid:
                    self.camera.setFormat7ConfigurationPacket(fmt7PktInfo.recommendedBytesPerPacket, image_mode)
            except PyCapture2.Fc2error as e:
                raise RuntimeError('Error configuring image settings') from e
        else:
            msg = """Camera does not support Format7, Mode 0 custom image
            configuration. This driver is therefore not compatible, as written."""
            raise RuntimeError(dedent(msg))
            
    def set_attribute(self, name, values):
        """Set the values of the attribute of the given name using the provided
        dictionary values. Typical structure is:
        values = {'onOff':True,
                  'autoManualMode':False,
                  'absControl':True,
                  'absValue':0.0}
        
        Note that invalid settings tend to coerce instead of error."""
        try:
            prop = self.camera.getProperty(getattr(PyCapture2.PROPERTY_TYPE,name))
            
            for key, val in values.items():
                setattr(prop,key,val)
            self.camera.setProperty(prop)
        except Exception as e:
            # Add some info to the exception:
            msg = f"failed to set attribute {name} to {values}"
            raise Exception(msg) from e
        
    def get_attributes(self, visibility_level, writeable_only=True):
        """Return a nested dict of all readable attributes.
        
        Structure is of form: {
            <Standard PROPERTY_TYPE>:{},
            'TriggerMode':{},
            'ImageMode':{}}
        """
        props = {}
        prop_names = {prop for prop in dir(PyCapture2.PROPERTY_TYPE) 
                      if not prop.startswith('_') 
                      and not prop == 'UNSPECIFIED_PROPERTY_TYPE'}
        
        props['TriggerMode'] = {}
        trig_mode = self.camera.getTriggerMode()            
        trig_props = [prop for prop in dir(trig_mode) 
                      if not prop.startswith('_')]
        props['ImageMode'] = {}
        image_mode, packetSize, percentage = self.camera.getFormat7Configuration()              
        image_props = [prop for prop in dir(image_mode) 
                      if not prop.startswith('_')]

        for name in prop_names:
            props[name] = self.get_attribute(name)
        
        for name in trig_props:
            props['TriggerMode'][name] = getattr(trig_mode,name)
        
        # read pixel format separately to get readable value
        if 'pixelFormat' in image_props:
            image_props.remove('pixelFormat')
            props['ImageMode']['pixelFormat'] = self.pixel_formats(image_mode.pixelFormat).name
        for name in image_props:
            props['ImageMode'][name] = getattr(image_mode,name)
            
        return props

    def get_attribute(self, name):
        """Return current values dictionary of attribute of the given name"""
        try:
            prop_dict = {}
            prop = self.camera.getProperty(getattr(PyCapture2.PROPERTY_TYPE,name))
            for key in self.get_props:
                prop_dict[key] = getattr(prop,key)
            return prop_dict
        except Exception as e:
            # Add some info to the exception:
            raise Exception(f"Failed to get attribute {name}") from e

    def snap(self):
        """Acquire a single image and return it"""
        
        self.configure_acquisition(continuous=False,bufferCount=1)
        image = self.grab()
        self.stop_acquisition()
        return image

    def configure_acquisition(self, continuous=True, bufferCount=10):
        """Configure acquisition buffer count and grab mode.
        Continuous mode only keeps most recent frames. Else, keep all frames.
        
        Also get returned image parameters for formatting purposes.
        """
        config = self.camera.getConfiguration()
        config.numBuffers = bufferCount
        if continuous:
            config.grabMode = PyCapture2.GRAB_MODE.DROP_FRAMES
            self.camera.setConfiguration(config)
        else:
            config.grabMode = PyCapture2.GRAB_MODE.BUFFER_FRAMES
            self.camera.setConfiguration(config)
            
        image_mode, packetSize, percentage = self.camera.getFormat7Configuration()

        self.width = image_mode.width
        self.height = image_mode.height
        self.pixelFormat = self.pixel_formats(image_mode.pixelFormat).name
            
        self.camera.startCapture()
            
    def grab(self):
        """Grab and return single image during pre-configured acquisition."""
        
        result = self.camera.retrieveBuffer()
        
        img = result.getData()
        #result.ReleaseBuffer(), exists in documentation, not PyCapture2
        
        return self._decode_image_data(img)

    def grab_multiple(self, n_images, images):
        """Grab n_images into images array during buffered acquistion."""
        print(f"Attempting to grab {n_images} images.")
        for i in range(n_images):
            while True:
                if self._abort_acquisition:
                    print("Abort during acquisition.")
                    self._abort_acquisition = False
                    return
                try:
                    images.append(self.grab())
                    print(f"Got image {i+1} of {n_images}.")
                    break
                except PyCapture2.Fc2error as e:
                    print('.', end='')
                    continue
        print(f"Got {len(images)} of {n_images} images.")
        
    def _decode_image_data(self,img):
        """FlyCapture2 image buffers require significant formatting.
        This returns what one would expect from a camera.
        configure_acquisition must be called first to set image format parameters."""
        pix_fmt = self.pixelFormat
        if pix_fmt.startswith('MONO'):
            if pix_fmt.endswith('8'):
                dtype = 'uint8'
            else:
                dtype = 'uint16'
            image = np.frombuffer(img,dtype=dtype).reshape(self.height,self.width)
        else:
            msg = """Only MONO image types currently supported.
            To add other image types, add conversion logic from returned 
            uint8 data to desired format in _decode_image_data() method."""
            raise ValueError(dedent(msg))
        return image.copy()

    def stop_acquisition(self):
        self.camera.stopCapture()

    def abort_acquisition(self):
        self._abort_acquisition = True

    def close(self):
        self.camera.disconnect()


class FlyCapture2CameraWorker(IMAQdxCameraWorker):
    """FlyCapture2 API Camera Worker. 
    
    Inherits from IMAQdxCameraWorker. Overloads get_attributes_as_dict 
    to use FlyCapture2Camera.get_attributes() method."""
    interface_class = FlyCapture2_Camera

    def get_attributes_as_dict(self, visibility_level):
        """Return a dict of the attributes of the camera for the given visibility
        level"""
        return self.camera.get_attributes(visibility_level)


