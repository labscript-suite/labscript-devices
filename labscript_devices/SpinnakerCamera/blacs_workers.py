#####################################################################
#                                                                   #
# /labscript_devices/SpinnakerCamera/blacs_workers.py               #
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
# PsSpin implementation by spe

import numpy as np
from labscript_utils import dedent
from enum import IntEnum
from time import sleep, perf_counter
import threading
import time
from blacs.tab_base_classes import ImageWorker
import PySpin


from labscript_devices.IMAQdxCamera.blacs_workers import IMAQdxCameraWorker

class Spinnaker_Camera(object):
    def __init__(self, serial_number):
        """Initialize Spinnaker API camera.

        Serial number should be of string(?) type."""
        global PySpin
        import PySpin

        self.system = PySpin.System.GetInstance()

        ver = self.system.GetLibraryVersion()
        min_ver = (1,23,0,27) # first release with python 3.6 support
        if (ver.major, ver.minor, ver.type, ver.build) < min_ver:
            raise RuntimeError(f"PySpin version {ver} must be >= {min_ver}")

        camList = self.system.GetCameras()
        numCams = camList.GetSize()

        if numCams==0:
            raise ValueError('No cameras found!')

        if isinstance(serial_number, int):
            self.camera = camList.GetBySerial('%d' % serial_number)
        else:
            self.camera = camList.GetBySerial(serial_number)
        self.camera.Init()
        camList.Clear()

        # Set the timeout to 5 s:
        self.timeout = 5000 # in ms

        # Set the abort acquisition thingy:
        self._abort_acquisition = False
        self.exception_on_failed_shot = True

    def get_attribute_names(self, visibility):
        names = []
        def get_node_names_in_category(node_category, prefix=''):
            for node_feature in node_category.GetFeatures():
                # Ensure node is available and readable
                if (not PySpin.IsAvailable(node_feature) or not
                    PySpin.IsReadable(node_feature)):
                    continue

                # Get the feature name:
                feature_name = node_feature.GetName()

                # Category nodes must be dealt with separately in order to retrieve subnodes recursively.
                if node_feature.GetPrincipalInterfaceType() == PySpin.intfICategory:
                    get_node_names_in_category(PySpin.CCategoryPtr(node_feature),
                                               prefix=feature_name + '::')
                else:
                    names.append(prefix + feature_name)

        node = self.camera.GetNodeMap()
        get_node_names_in_category(PySpin.CCategoryPtr(node.GetNode('Root')))

        return names

    def get_attribute(self, name, stream_map=False):
        """Return current values dictionary of attribute of the given name"""
        #print('Getting attribute %s.' % name)
        name = name.split('::')

        if stream_map:
            nodemap = self.camera.GetTLStreamNodeMap()
        else:
            nodemap = self.camera.GetNodeMap()
        node = nodemap.GetNode(name[-1])

        if PySpin.IsAvailable(node) and PySpin.IsReadable(node):
            if node.GetPrincipalInterfaceType() == PySpin.intfIInteger:
                return PySpin.CIntegerPtr(node).GetValue()
            elif node.GetPrincipalInterfaceType() == PySpin.intfIFloat:
                return PySpin.CFloatPtr(node).GetValue()
            elif node.GetPrincipalInterfaceType() == PySpin.intfIBoolean:
                return PySpin.CBooleanPtr(node).GetValue()
            else:
                return PySpin.CValuePtr(node).ToString()

    def set_attributes(self, attr_dict):
        for k, v in attr_dict.items():
            self.set_attribute(k, v)

    def set_stream_attribute(self, name, value):
        self.set_attribute(name, value, stream_map=True)

    def set_attribute(self, name, value, stream_map=False):
        #print('Setting attribute %s.' % name)
        name = name.split('::')

        if stream_map:
            nodemap = self.camera.GetTLStreamNodeMap()
        else:
            nodemap = self.camera.GetNodeMap()
        node = nodemap.GetNode(name[-1])

        if PySpin.IsAvailable(node) and PySpin.IsWritable(node):
            if node.GetPrincipalInterfaceType() == PySpin.intfIInteger:
                 PySpin.CIntegerPtr(node).SetValue(value)
            elif node.GetPrincipalInterfaceType() == PySpin.intfIFloat:
                 PySpin.CFloatPtr(node).SetValue(value)
            elif node.GetPrincipalInterfaceType() == PySpin.intfIBoolean:
                PySpin.CBooleanPtr(node).SetValue(value)
            else:
                PySpin.CValuePtr(node).FromString(value)

            sleep(0.05)
            # Sometimes this doesn't work, so let's check and print warnings if it
            # fails:
            name = '::'.join(name)
            return_value = self.get_attribute(name, stream_map=stream_map)
            if return_value != value:
                print('WARNING: setting attribute %s to %s failed. '%(name, str(value)) +
                      'Returned value %s instead'%str(return_value))
            else:
                print('Successfully set %s to %s.'%(name, str(return_value)))
        else:
            print('WARNING: not capable of writing attribute %s.'%'::'.join(name))


    def snap(self):
        """Acquire a single image and return it"""
        self.configure_acquisition(continuous=False, bufferCount=1)
        #self.trigger()
        image = self.grab()
        self.camera.EndAcquisition()
        return image

    def grab(self):
        """Grab and return single image during pre-configured acquisition."""
        #print('Grabbing...')
        image_result = self.camera.GetNextImage(self.timeout)
        img = self._decode_image_data(image_result.GetData())
        image_result.Release()
        return img

    def grab_multiple(self, n_images, images):
        """Grab n_images into images array during buffered acquistion."""
        print(f"Attempting to grab {n_images} images.")
        for i in range(n_images):
            if self._abort_acquisition:
                print("Abort during acquisition.")
                self._abort_acquisition = False
                return

            images.append(self.grab())
            print(f"Got image {i+1} of {n_images}.")
        print(f"Got {len(images)} of {n_images} images.")


    def trigger(self):
        """Execute software trigger"""
        nodemap = self.camera.GetNodeMap()
        trigger_cmd = PySpin.CCommandPtr(nodemap.GetNode('TriggerSoftware'))
        if not PySpin.IsAvailable(trigger_cmd) or not PySpin.IsWritable(trigger_cmd):
            print('WARNING: Unable to execute trigger. Aborting...')
        else:
            trigger_cmd.Execute()


    def configure_acquisition(self, continuous=True, bufferCount=10):
        self.pix_fmt = self.get_attribute('PixelFormat')
        self.height = self.get_attribute('Height')
        self.width = self.get_attribute('Width')

        # Unless the camera settings are set properly, in cntinuous mode
        # the camera will generally move faster than BLACS, and so the buffer
        # will fill up.  With a Flea3, I was unable to solve the prolem
        # easily.  It really is quite annoying.
        if continuous:
            self.set_stream_attribute('StreamBufferCountMode', 'Manual')
            self.set_stream_attribute('StreamBufferCountManual', bufferCount)
            self.set_stream_attribute('StreamBufferHandlingMode', 'NewestFirst')
            self.set_attribute('AcquisitionMode', 'Continuous')
        elif bufferCount == 1:
            # The StreamBufferCountMode originally was set to 'Auto', but this feature was depreciated by Spinnaker version 3.0.0.118
            self.set_stream_attribute('StreamBufferCountMode', 'Manual')
            self.set_stream_attribute('StreamBufferCountManual', 1)
            self.set_stream_attribute('StreamBufferHandlingMode', 'OldestFirst')
            self.set_attribute('AcquisitionMode', 'SingleFrame')
        else:
            self.set_stream_attribute('StreamBufferCountMode', 'Manual')
            self.set_stream_attribute('StreamBufferCountManual', bufferCount)
            self.set_stream_attribute('StreamBufferHandlingMode', 'OldestFirst')
            self.set_attribute('AcquisitionMode', 'MultiFrame')
            self.set_attribute('AcquisitionFrameCount', bufferCount)

        self.camera.BeginAcquisition()

    def _decode_image_data(self, img):
        """Spinnaker image buffers require significant formatting.
        This returns what one would expect from a camera.
        configure_acquisition must be called first to set image format parameters."""
        if self.pix_fmt.startswith('Mono'):
            if self.pix_fmt.endswith('8'):
                dtype = 'uint8'
            else:
                dtype = 'uint16'
            image = np.frombuffer(img, dtype=dtype).reshape(self.height, self.width)
        else:
            msg = """Only MONO image types currently supported.
            To add other image types, add conversion logic from returned
            uint8 data to desired format in _decode_image_data() method."""
            raise ValueError(dedent(msg))
        return image.copy()

    def stop_acquisition(self):
        print('Stopping acquisition...')
        self.camera.EndAcquisition()

        # This is supposed to provide debugging info, but as with most things
        # in PySpin, it appears to be completely useless:.
        num_frames=self.get_attribute('StreamTotalBufferCount', stream_map=True)
        failed_frames=self.get_attribute('StreamFailedBufferCount', stream_map=True)
        underrun_frames=self.get_attribute('StreamBufferUnderrunCount', stream_map=True)
        print('Stream info: %s frames acquired, %s failed, %s underrun' %
              (str(num_frames), str(failed_frames), str(underrun_frames)))

    def abort_acquisition(self):
        print('Stopping acquisition...')
        self._abort_acquisition = True

    def close(self):
        print('Closing down the camera...')
        self.camera.DeInit()
        self.camList.Clear()
        self.system.ReleaseInstance()

class SpinnakerCameraWorker(ImageWorker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.continuous_thread = None
        self._stop_event = threading.Event()
        self.camera = None
    
    def init(self):
        """Initialize the camera object"""
        system = PySpin.System.GetInstance()
        cam_list = system.GetCameras()
        if cam_list.GetSize() == 0:
            raise RuntimeError("No cameras detected")
        self.camera = cam_list[0]  # choose the first camera
        self.camera.Init()
        self.system = system
        self.cam_list = cam_list


    def init_camera(self, cam):
        """Initialize the camera object"""
        self.camera = cam
        self.camera.Init()

    def start_continuous(self, *args, **kwargs):
        """Start continuous acquisition in a separate thread"""
        if self.camera.IsStreaming():
            print("Camera already streaming. Skipping start_continuous.")
            return

        if self.continuous_thread is not None:
            # Thread already running
            return

        self._stop_event.clear()
        self.continuous_thread = threading.Thread(target=self._continuous_acquisition)
        self.continuous_thread.start()

    def _continuous_acquisition(self):
        try:
            self.camera.BeginAcquisition()
            while not self._stop_event.is_set():
                image = self.camera.GetNextImage(1000)
                if not image.IsIncomplete():
                    img_array = image.GetNDArray()
                    # Send live frame to BLACS GUI
                    self.send_image(img_array)
                image.Release()
        except PySpin.SpinnakerException as ex:
            print(f"Spinnaker exception: {ex}")
        finally:
            try:
                if self.camera.IsStreaming():
                    self.camera.EndAcquisition()
            except PySpin.SpinnakerException:
                pass

    def stop_continuous(self):
        """Stop continuous acquisition"""
        if self.continuous_thread is not None:
            self._stop_event.set()
            self.continuous_thread.join()
            self.continuous_thread = None

    def snap(self, *args, **kwargs):
        if self.camera is None:
            raise RuntimeError("Camera not initialized")

        try:
            if self.camera.IsStreaming():
                self.camera.EndAcquisition()
            self.camera.BeginAcquisition()

            image = self.camera.GetNextImage(1000)
            if not image.IsIncomplete():
                img_array = image.GetNDArray()
                # Send to BLACS GUI
                self.send_image(img_array)
            image.Release()

            self.camera.EndAcquisition()
        except PySpin.SpinnakerException as ex:
            print(f"Spinnaker exception during snap: {ex}")

    def shutdown(self):
        """Clean up camera on BLACS exit"""
        try:
            self.stop_continuous()
            if self.camera is not None:
                if self.camera.IsStreaming():
                    self.camera.EndAcquisition()
                self.camera.DeInit()
                del self.camera
        except PySpin.SpinnakerException as ex:
            print(f"Spinnaker exception during shutdown: {ex}")
    def program_manual(self, *args, **kwargs):
        """
        Called by BLACS when switching to manual mode.
        For now, this can be a no-op since we handle snapping via snap().
        """
        pass

    def abort(self):
        """Called by BLACS when aborting an experiment."""
        self.stop_continuous()


# class SpinnakerCameraWorker(IMAQdxCameraWorker):
#     """Spinnaker API Camera Worker.

#     Inherits from IMAQdxCameraWorker."""
#     interface_class = Spinnaker_Camera

#     def init(self):
#         self.continuous_thread = None
#         print("Spinnaker Worker Called")
#         try:
#             self.camera = self.interface_class(self.serial_number)
#             self.camera.configure_acquisition()
#             print(f"Successfully initialized camera {self.serial_number}")
#         except Exception as e:
#             print(f"Error initializing camera: {e}")
#             raise
    
#     def shutdown(self):
#         try:
#             self.camera.close()
#         except Exception as e:
#             print(f"Error shutting down camera: {e}")

#     def continuous_loop(self, dt):
#        """Acquire continuously in a loop, with minimum repetition interval dt"""
#        self.camera.trigger()
#        while True:
#            if dt is not None:
#                t = perf_counter()
#            image = self.camera.grab()
#            self.camera.trigger()
#            self._send_image_to_parent(image)
#            if dt is None:
#                timeout = 0
#            else:
#                timeout = t + dt - perf_counter()
#            if self.continuous_stop.wait(timeout):
#                self.continuous_stop.clear()
#                break
