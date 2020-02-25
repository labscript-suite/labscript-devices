#####################################################################
#                                                                   #
# /labscript_devices/PylonCamera/blacs_workers.py                   #
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
# Ported to Pylon API by dihm

import numpy as np
from labscript_utils import dedent

from labscript_devices.IMAQdxCamera.blacs_workers import IMAQdxCameraWorker

# Don't import API yet so as not to throw an error, allow worker to run as a dummy
# device, or for subclasses to import this module to inherit classes without requiring API
pylon = None
genicam = None

class Pylon_Camera(object):
    def __init__(self, serial_number):
        
        global pylon
        global genicam
        from pypylon import pylon, genicam
        
        factory = pylon.TlFactory.GetInstance()
        # Find and connect to camera:
        print("Connecting to camera...")
        sn = pylon.CDeviceInfo()
        sn.SetSerialNumber(str(serial_number))
        self.camera = pylon.InstantCamera(factory.CreateDevice(sn))
        self.camera.Open()
        self.timeout = 1000 # in ms
        self.camera.RegisterConfiguration(pylon.SoftwareTriggerConfiguration(),
                        pylon.RegistrationMode_ReplaceAll, pylon.Cleanup_Delete)
        # Keep a nodeMap reference so we don't have to re-create a lot
        self.nodeMap = self.camera.GetNodeMap()
        self._abort_acquisition = False

    def set_attributes(self, attributes_dict):
        """Sets all attribues in attr_dict.
        Pylon cameras require that ROI settings be done in correct order,
        so we do them separately."""
        # make a copy of dict so we can pop off already handled values
        attr_dict = attributes_dict.copy()
        ROIx = ['Width','OffsetX']
        ROIy = ['Height','OffsetY']
        if set(ROIx).issubset(attr_dict):
            if attr_dict['OffsetX'] <= (self.camera.WidthMax()-self.camera.Width()):
                ROIx.reverse()
            ROIx_settings = [attr_dict.pop(k) for k in ROIx]
            for k,v in zip(ROIx,ROIx_settings):
                self.set_attribute(k, v)
        
        if set(ROIy).issubset(attr_dict):
            if attr_dict['OffsetY'] <= (self.camera.HeightMax()-self.camera.Height()):
                ROIy.reverse()
            ROIy_settings = [attr_dict.pop(k) for k in ROIy]
            for k,v in zip(ROIy,ROIy_settings):
                self.set_attribute(k, v)
        
        for k, v in attr_dict.items():
            self.set_attribute(k, v)

    def set_attribute(self, name, value):
        """Set the value of the attribute of the given name to the given value"""
        try:
            self.nodeMap.GetNode(name).SetValue(value)
        except Exception as e:
            # Add some info to the exception:
            msg = f"failed to set attribute {name} to {value}"
            raise Exception(msg) from e
        
    def get_attributes(self, visibility_level, writeable_only=True):
        """Return a dict of all attributes of readable attributes, for the given
        visibility level. Optionally return only writeable attributes.
        """
        visibilities = {
            'simple': ['Beginner'],
            'intermediate': ['Beginner','Expert'],
            'advanced': ['Beginner','Expert','Guru'],
        }
        if writeable_only:
            modes = ['RW']
        else:
            modes = ['RW','RO']
        visibility_level = visibilities[visibility_level.lower()]
        attributes = []
        filters = [lambda n: n.GetNode().IsFeature(),
                   lambda n:genicam.EVisibilityClass.ToString(n.GetNode().GetVisibility()) in visibility_level,
                   lambda n:genicam.EAccessModeClass.ToString(n.GetNode().GetAccessMode()) in modes]
        params = filter(lambda n: all([f(n) for f in filters]), self.nodeMap.GetNodes())
        attributes = {}
        for n in params:
            try:
                attributes[n.GetNode().GetName()] = n.GetValue()
            except AttributeError:
                attributes[n.GetNode().GetName()] = n.ToString()
        return attributes

    def get_attribute(self, name):
        """Return current value of attribute of the given name"""
        try:
            return self.nodeMap.GetNode(name).GetValue()
        except Exception as e:
            # Add some info to the exception:
            raise Exception(f"Failed to get attribute {name}") from e

    def snap(self):
        """Acquire a single image and return it"""
        result = self.camera.GrabOne(self.timeout,
                                     pylon.TimeoutHandling_ThrowException)
        if result.GrabSucceeded():
            img = result.Array
            result.Release()
            return img
        else:
            raise('Snap Error:',result.ErrorCode,result.ErrorDescription)

    def configure_acquisition(self, continuous=True, bufferCount=10):
        """Configure acquisition by calling StartGrabbing with appropriate
        grab strategy: LatestImageOnly for continuous, OneByOne otherwise.
        """
        self.camera.MaxNumBuffer = bufferCount
        if continuous:
            self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
        else:
            self.camera.StartGrabbing(pylon.GrabStrategy_OneByOne)

    def grab(self, continuous=True):
        """Grab single image during pre-configured acquisition."""
            
        result = self.camera.RetrieveResult(self.timeout,
                                        pylon.TimeoutHandling_ThrowException)
        if result.GrabSucceeded():
            img = result.Array
            result.Release()
            return img
        else:
            raise('Grab Error:',result.ErrorCode,result.ErrorDescription)

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
                    images.append(self.grab(continuous=False))
                    print(f"Got image {i+1} of {n_images}.")
                    break
                except pylon.TimeoutException as e:
                    print('.', end='')
                    continue
        print(f"Got {len(images)} of {n_images} images.")

    def stop_acquisition(self):
        self.camera.StopGrabbing()

    def abort_acquisition(self):
        self._abort_acquisition = True

    def close(self):
        self.camera.Close()


class PylonCameraWorker(IMAQdxCameraWorker):
    """Pylon API Camera Worker. 
    
    Inherits from IMAQdxCameraWorker. Overloads get_attributes_as_dict 
    to use PylonCamera.get_attributes() method."""
    interface_class = Pylon_Camera

    def get_attributes_as_dict(self, visibility_level):
        """Return a dict of the attributes of the camera for the given visibility
        level"""
        return self.camera.get_attributes(visibility_level)


