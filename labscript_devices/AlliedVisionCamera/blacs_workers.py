#####################################################################
#                                                                   #
# /labscript_devices/AlliedVisionCamera/blacs_workers.py            #
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
# VmbPy implementation by qredon

import numpy as np
from enum import IntEnum
from queue import Queue
from labscript_utils import dedent

import os
import sys

import logging
logger = logging.getLogger("AlliedVision_Camera")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(handler)


from labscript_devices.IMAQdxCamera.blacs_workers import IMAQdxCameraWorker

# Don't import API yet so as not to throw an error, allow worker to run as a dummy
# device, or for subclasses to import this module to inherit classes without requiring API
vmbpy = None

# Set correct path for VmbStartup before importing vmbpy: necessary in isolated environment (e.g., BLACS or Jupyter)
# Root of the Vimba X installation
os.environ["VIMBA_X_X_PATH"] = r"C:\Program Files\Allied Vision\Vimba X"
# Explicitly tell GenTL where to look for CTI files
os.environ["GENICAM_GENTL64_PATH"] = r"C:\Program Files\Allied Vision\Vimba X\cti"

# Frame Handler needed in stream mode to handle each image arriving in the buffer.
class Handler:
    def __init__(self, buffer_count):
        self.display_queue = Queue(buffer_count)

    def get_image(self, timeout):
        return self.display_queue.get(True, timeout)

    def __call__(self, cam: "Camera", stream: "Stream", frame: "Frame"):
        if frame.get_status() == vmbpy.FrameStatus.Complete:
            logger.debug(f'{cam} acquired {frame}')
            
            self.display_queue.put(frame)

        cam.queue_frame(frame)

def int_to_camera_id(cam_int: int) -> str:
    """Convert the integer ID back to the original string."""
    # Calculate how many bytes are needed to represent the integer
    length = (cam_int.bit_length() + 7) // 8
    return cam_int.to_bytes(length, byteorder='big').decode('utf-8')

class AlliedVision_Camera(object):
    """The backend hardware interface class for the AlliedVisionCamera.
    
    This class handles all of the API/hardware implementation details for the
    corresponding labscript device. It is used by the BLACS worker to send
    appropriate API commands to the camera for the standard BLACS camera operations
    (i.e. transition_to_buffered, get_attributes, snap, etc).
    """
    def __init__(self,serial_number):
        """Initialize VmbPy API camera.
            Serial number should be of string type."""
        global vmbpy
        import vmbpy
        # Enter Vimba system and open camera
        self.vmb = vmbpy.VmbSystem.get_instance()
        self.vmb.__enter__()

        camList = self.vmb.get_all_cameras()
        numCams= len(camList)
        if numCams==0:
            raise ValueError("No AlliedVision cameras detected!")
        else:
            # Look up camera by ID
            try:
                cam_id_str = int_to_camera_id(serial_number)
                self.cam = self.vmb.get_camera_by_id(cam_id_str)
                logger.info(f'Opening camera S/N:{cam_id_str}')
            except:
                camId = [cam.get_id() for cam in camList]
                raise ValueError(f'Failed to connect to camera {cam_id_str}. Available camera: {camId}')
                
        # Open camera context
        self.cam.__enter__()
          
        # Prepare for acquisition
        self._abort_acquisition = False
        self.exception_on_failed_shot = True
    
        # # Set the timeout to 5 s:
        self.timeout_s = 5 # in s

    def show_attributes(self, visibility_level, writable_only=True):
        """Print all camera attributes filtered by visibility and writability.
        Args:
            writable_only (bool, optional): If True, only include writable features.
        Print:
            feature_name: 'value': <> | 'visibility': <> | 'writable': <> | 'readable': <>
        """

        VALID_LEVELS_MAP = {
            'Simple': vmbpy.FeatureVisibility.Beginner,
            'Intermediate': vmbpy.FeatureVisibility.Expert,
            'Advanced': vmbpy.FeatureVisibility.Guru
        }
        
        if visibility_level not in VALID_LEVELS_MAP.keys():
            raise ValueError(f"Invalid visibility level '{visibility_level}'. Must be one of {VALID_LEVELS_MAP.keys()}")
            
        max_visibility_level = VALID_LEVELS_MAP[visibility_level]
        
        attrs = {}
        
        features = self.cam.get_all_features()
            
    
        for feat in features:
            vis = feat.get_visibility()
            if vis <= max_visibility_level:
                # write filtering
                if writable_only and not feat.is_writeable():
                    continue
    
                name = feat.get_name()
                is_readable = feat.is_readable()
                # Safely try to get value if readable
                try:
                    # Read command status
                    if isinstance(feat, vmbpy.feature.CommandFeature):
                        value = feat.is_done()
                        if value:
                            value = 'Done'
                        else:
                            value = 'Being executed'
                    # binary blob, rarely used (needs to be decoded)      
                    elif isinstance(feat,  vmbpy.feature.RawFeature):
                        value = np.frombuffer(feat.get(), dtype='uint16')
                    # usually set/read via enum entry name
                    elif isinstance(feat,  vmbpy.feature.EnumFeature):
                        entry = feat.get() if is_readable else '<Not readable>'
                        value = entry.as_tuple()[0] # retrieve str entry 
                    # int,str,float attributes
                    else:
                        value = feat.get() if is_readable else '<Not readable>'
            
                except Exception as e:
                    value = '<Error>'
                    # Add some info to the exception:
                    raise Exception(f"Failed to get attribute {name}") from e   
                    
                attrs[name] = {
                    'value': value,
                    'visibility': visibility_level,
                    'readable': feat.is_readable(),
                    'writable': feat.is_writeable()
                }
        
        for name, info in attrs.items():
            print(f"{name:30s} | {info['value']} | {info['visibility']} | readable = {info['readable']} | writable={info['writable']}")          
        
        return None

    def get_attribute_names(self, visibility_level, writable_only=True):
        """Return a list camera attributes filtered by visibility and writability.
        Args:
            writable_only (bool, optional): If True, only include writable features.
        Returns:
            list: [feature_names]
        """
        
        VALID_LEVELS_MAP = {
            'Simple': vmbpy.FeatureVisibility.Beginner,
            'Intermediate': vmbpy.FeatureVisibility.Expert,
            'Advanced': vmbpy.FeatureVisibility.Guru
        }
        
        if visibility_level not in VALID_LEVELS_MAP.keys():
            raise ValueError(f"Invalid visibility level '{visibility_level}'. Must be one of {VALID_LEVELS_MAP.keys()}")
            
        max_visibility_level = VALID_LEVELS_MAP[visibility_level]
        
        attr_names = []
    
        for feat in self.cam.get_all_features():
            vis = feat.get_visibility()
            if vis <= max_visibility_level:
                # write filtering
                if writable_only and not feat.is_writeable():
                    continue

                name = feat.get_name()
                attr_names.append(name)
                          
        return attr_names

    def get_attribute(self, name):
        """Return a single camera attribute.
        Args:
            name (str): Name of the camera feature to query.
        Returns:
            attribute value
        """
        
        try:
            feat = self.cam.get_feature_by_name(name)
        except Exception:
            logger.warning(f"Feature '{name}' not found.")
            return None
    
        is_readable = feat.is_readable()

        # Safely try to get value if readable
        try:
            # Read command status
            if isinstance(feat, vmbpy.feature.CommandFeature):
                value = feat.is_done()
            # binary blob, rarely used (needs to be decoded)      
            elif isinstance(feat,  vmbpy.feature.RawFeature):
                value = np.frombuffer(feat.get(), dtype='uint16')
            # usually set/read via enum entry name
            elif isinstance(feat,  vmbpy.feature.EnumFeature):
                current_entry = feat.get() if is_readable else '<Not readable>'
                value = current_entry.as_tuple()[0] # retrieve str entry 
            # int,str,bool,float attribute types
            else:
                value = feat.get() if is_readable else '<Not readable>'
    
        except Exception as e:
            # Add some info to the exception:
            raise Exception(f"Failed to get attribute {name}: {e}")
    
        return value

    def get_available_EnumEntries(self,name):
        try:
            feat = self.cam.get_feature_by_name(name)
        except Exception:
            logger.warning(f"Feature '{name}' not found.")
            return None
            
        try:
            available_entries = feat.get_available_entries()
            available_entries = [entry.as_tuple()[0] for entry in available_entries]
            
        except Exception as e:
            # Add some info to the exception:
            raise Exception(f" Note a valid EnumFeature: {e}")
            
        return available_entries
        
    def set_attribute(self, name, value):
        """Set a single camera attribute, with type safety and visibility checks.
        Args:
            name (str): Name of the camera feature to set.
            value (any): Value to assign. For Enum or Command features, use strings.
        Returns:
            bool: True if successfully set or executed, False otherwise.
        """
        FEATURE_TYPE_MAP = {
            vmbpy.feature.IntFeature: int,
            vmbpy.feature.FloatFeature: float,
            vmbpy.feature.BoolFeature: bool,
            vmbpy.feature.EnumFeature: str,      # usually set/read via enum entry name
            vmbpy.feature.StringFeature: str,
            vmbpy.feature.CommandFeature: bool,  # trigger/run via True or 'run'
            vmbpy.feature.RawFeature: bytes,     # binary blob, rarely used
        }
        
        # Attempt to retrieve feature
        try:
            feat = self.cam.get_feature_by_name(name)
        except Exception:
            logger.warning(f"Feature '{name}' not found on this camera.")
            return False
    
        if not feat.is_writeable():
            logger.warning(f"Feature '{name}' is not writable.")
            return False
    
        ftype = feat.get_type()
        try:
            # Handle by type
            # Command-type features must be triggered, not assigned
            if isinstance(feat, vmbpy.feature.CommandFeature):
                if isinstance(value,FEATURE_TYPE_MAP[ftype]) and value:
                    feat.run()
                    logger.debug(f"Command '{name}' executed.")
                    return True
                else:
                    logger.warning(f"Command feature '{name}' not executed (input bool value: {value}).")
                    return False
            # usually set/read via enum entry name (str)
            elif isinstance(feat, vmbpy.feature.EnumFeature) and isinstance(value,FEATURE_TYPE_MAP[ftype]):
                available_entries = feat.get_available_entries()
                available_entries = [entry.as_tuple()[0] for entry in available_entries]
                if value in available_entries:
                    feat.set(value)
                else:
                    logger.warning(f"Enum feature '{name}' should be one of those strings '{available_entries}'.")
                    return False
            # binary blob, rarely used (needs to be encoded ) not tested      
            # elif isinstance(feat,  vmbpy.feature.RawFeature) and isinstance(value,FEATURE_TYPE_MAP[ftype]):
            #     value_encoded = value.encode('utf8')
            #     feat.set(value_encoded)
            # else int, float, bool, str type input 
            elif isinstance(value,FEATURE_TYPE_MAP[ftype]):
                feat.set(value)
            else:
                logger.warning(f"Unsupported feature type '{ftype}' for '{name}'.")
                return False
                
            logger.debug(f"Set {name} = {value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set '{name}' to {value}: {e}")
            return False
            
    def set_attributes(self, attr_dict):
        for k, v in attr_dict.items():
            self.set_attribute(k, v)

    def configure_acquisition(self, continuous=True, buffer_count=10):
        """Configure and prepare the camera for acquisition.
        Args:
            continuous (bool): If True, camera runs continuously.
                               If False, single-frame mode or multi-frame mode.
            buffer_count (int): Number of frame buffers to queue.
        """
        if not self.cam:
            raise RuntimeError("Camera is not open or initialized.")

        # Set acquisition mode
        if continuous:
            self.set_attribute("AcquisitionMode", "Continuous")
        elif buffer_count == 1 and not continuous:
            self.set_attribute("AcquisitionMode","SingleFrame")
        else:
            self.set_attribute("AcquisitionMode","MultiFrame")
        
        # Store image format info for later decoding
        self.width = self.get_attribute("Width")
        self.height = self.get_attribute("Height")
        self.pixel_format = self.get_attribute("PixelFormat")
        
        # Prepare stream
        self._buffer_count = buffer_count
        self.handler = Handler(buffer_count)
        self.cam.start_streaming(self.handler, buffer_count)
    
        logger.info(f"Acquisition configured: {self.width}x{self.height}, {self.pixel_format}")
        
    def grab(self):
        """ Grab and return single image during pre-configured acquisition
        Returns:
            numpy.array: Acquired image
        """
        img = self.handler.get_image(self.timeout_s)
        img = img.as_numpy_ndarray().reshape(self.height,self.width)
        return img

    def snap(self):
        """ Acquire a single image and return it
        Returns:
            numpy.array: Acquired image
        """
        logger.info("Snapping single image...")
        self.configure_acquisition(continuous=False, buffer_count=1)
        img = self.grab()
        self.cam.stop_streaming()
        return img
        
    def grab_multiple(self, n_images, images):
        """Grab n_images into images array during buffered acquistion.
        Args:
            n_images (int): Number of captured images.
            images (list): Empty list to fill with images
        """
        logger.info(f"Attempting to grab {n_images} images.")
        for i in range(n_images):
            if self._abort_acquisition:
                logger.warning("Abort during acquisition.")
                self._abort_acquisition = False
                return

            images.append(self.grab())
            logger.debug(f"Got image {i+1} of {n_images}.")
        logger.info(f"Got {len(images)} of {n_images} images.")
        self.stop_acquisition()
    
    def stop_acquisition(self):
        """Stop streaming of camera"""
        if self.cam.is_streaming():
            self.cam.stop_streaming()
            logger.info('Stopping acquisition...')

    def abort_acquisition(self):
        """Set _abort_acquisition to True"""
        logger.info('Aborting acquisition...')
        self._abort_acquisition = True

    def close(self):
        self.cam.close()
        self.vmb.__exit__(None, None, None)
        
    def close(self):
        """Safely stop acquisition, release buffers, and close the camera connection."""
        if self.cam is None:
            return
            
        # Stop acquisition if running
        if self.cam.is_streaming():
            self.stop_acquisition()
            
        # Close the camera
        self.cam.__exit__(None, None, None)
        self.cam = None

        # Close vmb system
        self.vmb.__exit__(None, None, None)
        self.vmb = None

        logger.info("Camera connection closed.")


class AlliedVisionCameraWorker(IMAQdxCameraWorker):
    """AlliedVision API Camera Worker.

    Inherits from IMAQdxCameraWorker."""
    interface_class = AlliedVision_Camera