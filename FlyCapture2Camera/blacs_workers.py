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
    """The backend hardware interface class for the FlyCapture2Camera.
    
    This class handles all of the API/hardware implementation details for the
    corresponding labscript device. It is used by the BLACS worker to send
    appropriate API commands to the camera for the standard BLACS camera operations
    (i.e. transition_to_buffered, get_attributes, snap, etc).
    
    Attributes:
        camera (PyCapture2.Camera): Handle to connected camera.
        get_props (list): This list sets which values of each property object 
            are returned when queried by :obj:`get_attribute`.
        pixel_formats (IntEnum): An IntEnum object that is automatically 
            populated with the supported pixel types of the connected camera.
        width (int): Width of images for most recent acquisition. 
            Used by :obj:`_decode_image_data` to format images correctly.
        height (int): Height of images for most recent acquisition.
            Used by :obj:`_decode_image_data` to format images correctly.
        pixelFormat (str): Pixel format name for most recent acquisition.
            Used by :obj:`_decode_image_data` to format images correctly.
        _abort_acquisition (bool): Abort flag that is polled during buffered
            acquisitions.
    """
    def __init__(self, serial_number):
        """Initialize FlyCapture2 API camera.
        
        Searches all cameras reachable by the host using the provided serial
        number. Fails with API error if camera not found.
        
        This function also does a significant amount of default configuration.
        
        * It defaults the grab timeout to 1 s
        * Ensures use of the API's HighPerformanceRetrieveBuffer
        * Ensures the camera is in Format 7, Mode 0 with full frame readout and MONO8 pixels
        * If using a GigE camera, automatically maximizes the packet size and warns if Jumbo packets are not enabled on the NIC
        
        Args:
            serial_number (int): serial number of camera to connect to
        """
        
        global PyCapture2
        import PyCapture2
        
        ver = PyCapture2.getLibraryVersion()
        min_ver = (2,12,3,31) # first release with python 3.6 support
        if ver < min_ver:
            raise RuntimeError(f"PyCapture2 version {ver} must be >= {min_ver}")
        
        print('Connecting to SN:%d ...'%serial_number)
        bus = PyCapture2.BusManager()
        self.camera = PyCapture2.Camera()
        self.camera.connect(bus.getCameraFromSerialNumber(serial_number))
        
        # set which values of properties to return
        self.get_props = ['present','absControl','absValue',
                          'onOff','autoManualMode',
                          'valueA','valueB']
        
        fmts = {prop:getattr(PyCapture2.PIXEL_FORMAT,prop) 
                for prop in dir(PyCapture2.PIXEL_FORMAT) 
                if not prop.startswith('_')}
                
        self.pixel_formats = IntEnum('pixel_formats',fmts)

        self._abort_acquisition = False
        
        # check if GigE camera. If so, ensure max packet size is used
        cam_info = self.camera.getCameraInfo()
        if cam_info.interfaceType == PyCapture2.INTERFACE_TYPE.GIGE:
            # need to close generic camera first to avoid strange interactions
            print('Checking Packet size for GigE Camera...')
            self.camera.disconnect()
            gige_camera = PyCapture2.GigECamera()
            gige_camera.connect(bus.getCameraFromSerialNumber(serial_number))
            mtu = gige_camera.discoverGigEPacketSize()
            if mtu <= 1500:
                msg = """WARNING: Maximum Transmission Unit (MTU) for ethernet 
                NIC FlyCapture2_Camera SN:%d is connected to is only %d. 
                Reliable operation not expected. 
                Please enable Jumbo frames on NIC."""
                print(dedent(msg%(serial_number,mtu)))
            
            gige_pkt_size = gige_camera.getGigEProperty(PyCapture2.GIGE_PROPERTY_TYPE.GIGE_PACKET_SIZE)
            # only set if not already at correct value
            if gige_pkt_size.value != mtu:
                gige_pkt_size.value = mtu
                gige_camera.setGigEProperty(gige_pkt_size)
                print('  Packet size set to %d'%mtu)
            else:
                print('  GigE Packet size is %d'%gige_pkt_size.value)
            
            # close GigE handle to camera, re-open standard handle
            gige_camera.disconnect()
            self.camera.connect(bus.getCameraFromSerialNumber(serial_number))
            
        # set standard device configuration
        config = self.camera.getConfiguration()
        config.grabTimeout = 1000 # in ms
        config.highPerformanceRetrieveBuffer = True
        self.camera.setConfiguration(config)

        # ensure camera is in Format7,Mode 0 custom image mode
        fmt7_info, supported = self.camera.getFormat7Info(0)
        if supported:
            # to ensure Format7, must set custom image settings
            # defaults to full sensor size and 'MONO8' pixel format
            print('Initializing to default Format7, Mode 0 configuration...')
            fmt7_default = PyCapture2.Format7ImageSettings(0,0,0,fmt7_info.maxWidth,fmt7_info.maxHeight,self.pixel_formats['MONO8'].value)
            self._send_format7_config(fmt7_default)
            
        else:
            msg = """Camera does not support Format7, Mode 0 custom image
            configuration. This driver is therefore not compatible, as written."""
            raise RuntimeError(dedent(msg))

    def set_attributes(self, attr_dict):
        """Sets all attribues in attr_dict.
        
        FlyCapture does not control all settings through same interface,
        so we must do them separately.
        Interfaces are: <Standard PROPERTY_TYPE>, TriggerMode, ImageMode
            
        Args:
            attr_dict (dict): dictionary of property dictionaries to set for the camera.
                These property dictionaries assume a specific structure, outlined in
                :obj:`set_attribute`, :obj:`set_trigger_mode` and , :obj:`set_image_mode`
                methods.
        """
        
        for prop, vals in attr_dict.items():
            if prop == 'TriggerMode':
                self.set_trigger_mode(vals)
                
            elif prop == 'ImageMode':
                self.set_image_mode(vals)
                
            else:
                self.set_attribute(prop, vals)
                
    def set_trigger_mode(self,trig_dict):
        """Configures triggering options via Trigger Mode interface.
        
        Args:
            trig_dict (dict): dictionary with trigger mode property settings. Allowed keys:
                
                * 'onOff': bool
                * 'polarity': 0,1
                * 'source': int
                * 'mode': int
                
        """
        trig_mode = self.camera.getTriggerMode()
        for k,v in trig_dict.items():
            setattr(trig_mode,k,v)
        
        try:
            self.camera.setTriggerMode(trig_mode)
        except Exception as e:
            msg = "Failed to set Trigger Mode!"
            raise Exception(msg) from e
            
    def set_image_mode(self,image_settings):
        """Configures ROI and image control via Format 7, Mode 0 interface.
        
        Args:
            image_settings (dict): dictionary of image settings. Allowed keys:
                
                * 'pixelFormat': valid pixel format string, i.e. 'MONO8'
                * 'offsetX': int
                * 'offsetY': int
                * 'width': int
                * 'height': int
        """
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
                
            self._send_format7_config(image_mode)
            
        else:
            msg = """Camera does not support Format7, Mode 0 custom image
            configuration. This driver is therefore not compatible, as written."""
            raise RuntimeError(dedent(msg))
            
    def set_attribute(self, name, values):
        """Set the values of the attribute of the given name using the provided
        dictionary values. 
        
        Generally, absControl should be used to configure settings. Note that
        invalid settings tend to coerce instead of presenting an error.
        
        Args:
            name (str): 
            values (dict): Dictionary of settings for the property. Allowed keys are:
                
                * 'onOff': bool
                * 'autoManualMode': bool
                * 'absControl': bool
                * 'absValue': float
                * 'valueA': int
                * 'valueB': int
                * 'onePush': bool
        """
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
        
        Args:
            visibility_level (str): Not used.
            writeable_only (:obj:`bool`, optional): Not used
            
        Returns:
            dict: Dictionary of property dictionaries
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
        """Return current values dictionary of attribute of the given name.
        
        Args:
            name (str): Property name to read
            
        Returns:
            dict: Dictionary of property values with structure as defined in
                :obj:`set_attribute`.
        """
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
        """Acquire a single image and return it
        
        Returns:
            numpy.array: Acquired image
        """
        
        self.configure_acquisition(continuous=False,bufferCount=1)
        image = self.grab()
        self.stop_acquisition()
        return image

    def configure_acquisition(self, continuous=True, bufferCount=10):
        """Configure acquisition buffer count and grab mode.
        
        This method also saves image width, heigh, and pixelFormat to class
        attributes for returned image formatting.
        
        Args:
            continuous (:obj:`bool`, optional): If True, camera will continuously
                acquire and only keep most recent frames in the buffer. If False,
                all acquired frames are kept and error occurs if buffer is exceeded.
                Default is True.
            bufferCount (:obj:`int`, optional): Number of memory buffers to use 
                in the acquistion. Default is 10.
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
        """Grab and return single image during pre-configured acquisition.
        
        Returns:
            numpy.array: Returns formatted image
        """
        
        result = self.camera.retrieveBuffer()
        
        img = result.getData()
        #result.ReleaseBuffer(), exists in documentation, not PyCapture2
        
        return self._decode_image_data(img)

    def grab_multiple(self, n_images, images):
        """Grab n_images into images array during buffered acquistion.
        
        Grab method involves a continuous loop with fast timeout in order to
        poll :obj:`_abort_acquisition` for a signal to abort.
        
        Args:
            n_images (int): Number of images to acquire. Should be same number
                as the bufferCount in :obj:`configure_acquisition`.
            images (list): List that images will be saved to as they are acquired
        """
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
        """Formats returned FlyCapture2 API image buffers.
        
        FlyCapture2 image buffers require significant formatting.
        This returns what one would expect from a camera.
        :obj:`configure_acquisition` must be called first to set image format parameters.
        
        Args:
            img (numpy.array): A 1-D array image buffer of uint8 values to format
            
        Returns:
            numpy.array: Formatted array based on :obj:`width`, :obj:`height`, 
                and :obj:`pixelFormat`.
        """
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
        
    def _send_format7_config(self,image_config):
        """Validates and sends the Format7 configuration packet.
        
        Args:
            image_config (PyCapture2.Format7ImageSettings): Format7ImageSettings
                object to validate and send to camera.
        """
        try:            
            fmt7PktInfo, valid = self.camera.validateFormat7Settings(image_config)
            if valid:
                self.camera.setFormat7ConfigurationPacket(fmt7PktInfo.recommendedBytesPerPacket, image_config)
        except PyCapture2.Fc2error as e:
            raise RuntimeError('Error configuring image settings') from e

    def stop_acquisition(self):
        """Tells camera to stop current acquistion."""
        self.camera.stopCapture()

    def abort_acquisition(self):
        """Sets :obj:`_abort_acquisition` flag to break buffered acquisition loop."""
        self._abort_acquisition = True

    def close(self):
        """Closes :obj:`camera` handle to the camera."""
        self.camera.disconnect()


class FlyCapture2CameraWorker(IMAQdxCameraWorker):
    """FlyCapture2 API Camera Worker. 
    
    Inherits from obj:`IMAQdxCameraWorker`. Defines :obj:`interface_class` and overloads
    :obj:`get_attributes_as_dict` to use FlyCapture2Camera.get_attributes() method."""
    interface_class = FlyCapture2_Camera

    def get_attributes_as_dict(self, visibility_level):
        """Return a dict of the attributes of the camera for the given visibility
        level
        
        Args:
            visibility_level (str): Normally configures level of attribute detail
                to return. Is not used by FlyCapture2_Camera.
        """
        if self.mock:
            return IMAQdxCameraWorker.get_attributes_as_dict(self,visibility_level)
        else:
            return self.camera.get_attributes(visibility_level)


