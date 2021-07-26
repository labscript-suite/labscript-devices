FlyCapture2 Cameras
===================

This device allows control of FLIR (formerly Point Grey) scientific cameras via the `FlyCapture2 SDK <https://www.flir.com/products/flycapture-sdk/>`_ with the now deprecated PyCapture2 wrapper.
In order to use this device, both the SDK and the python wrapper must be installed.
Note that PyCapture2 only supports up to Python 3.6.

The new FLIR SDK is supported using the :doc:`SpinnakerCamera labscript device <spinnaker>`.

.. autosummary::
   labscript_devices.FlyCapture2Camera.labscript_devices
   labscript_devices.FlyCapture2Camera.blacs_tabs
   labscript_devices.FlyCapture2Camera.blacs_workers

Installation
~~~~~~~~~~~~

First ensure that the FlyCapture2 SDK is installed. 

The python wrapper is available via FLIR and is only released for Python up to 3.6.
It must be installed separately, pointed to the correct conda environment during install.


For GigE cameras, ensure that the network interface card (NIC) on the computer with the BLACS controlling the camera has enabled Jumbo Frames.
That maximum allowed value (typically 9000) is preferable to avoid dropped frames.

Usage
~~~~~

Like the :doc:`IMAQdxCamera <IMAQdx>` device, the bulk of camera configuration is performed using a dictionary of kwargs, where the key names and values mirror those provided by the FlyCapture2 SDK interface.
Which parameters can/need to be set depend on the communication interface.
Discovery of what parameters are available can be done in three ways:

1. Careful reading of the FlyCapture2 SDK docs.
2. Mirroring the FlyCap Viewer parameter names and values.
3. Connecting to the camera with a minimal configuration, viewing the current parameters dictionary, and copying the relevant values to the connection table (preferred).

The python structure for setting these values differs somewhat from other camera devices in labscript, taking the form of nested dictionaries.
This structure most closely matches the structure of the FlyCapture2 SDK in that each camera property has multiple sub-elements that control the feature.
In this implementation, the standard camera properties are set using keys with ALL CAPS.
The control of the Trigger Mode and Image Mode properties is handled separately, using a slightly different nesting structure than the other properties.

Below is a generic configuration for a Point Grey Blackfly PGE-23S6M-C device.

.. code-block:: python

   from labscript import *
   
   from labscript_devices.FlyCapture2Camera.labscript_devices import FlyCapture2Camera

   FlyCapture2Camera('gigeCamera',parent_device=parent,connection=conn,
               serial_number=1234567, # set to the camera serial number
               minimum_recovery_time=36e-6, # the minimum exposure time depends on the camera model & configuration
               camera_attributs={
                                 'GAMMA':{
                                          'onOff':False,
                                          'absControl':True,
                                          'absValue':1},
                                 'AUTO_EXPOSURE':{
                                          'onOff':True,
                                          'absControl':True,
                                          'autoManualMode':False,
                                          'absValue':0},
                                 'GAIN':{
                                          'autoManualMode':False,
                                          'absControl':True,
                                          'absValue':0},
                                 'SHARPNESS':{
                                          'onOff':False,
                                          'autoManualMode':False,
                                          'absValue':1024},
                                 'FRAME_RATE':{
                                          'autoManualMode':False,
                                          'absControl':True},
                                 'SHUTTER':{
                                          'autoManualMode':False,
                                          'absValue':0},
                                 'TriggerMode':{
                                          'polarity':1,
                                          'source':0,
                                          'mode':1,
                                          'onOff':True},
                                 'ImageMode':{
                                          'width':1920,
                                          'height':1200,
                                          'offsetX':0,
                                          'offsetY':0,
                                          'pixelFormat':'MONO16'}
               },
               manual_camera_attributes={'TriggerMode':{'onOff':False}})

   start()

   gigeCamera.expose(t=0.5,'exposure1')


   stop(1)


Detailed Documentation
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: labscript_devices.FlyCapture2Camera
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.FlyCapture2Camera.labscript_devices
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.FlyCapture2Camera.blacs_tabs
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.FlyCapture2Camera.blacs_workers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:
