Spinnaker Cameras
=================

This device allows control of FLIR scientific cameras via the `Spinnaker SDK <https://www.flir.com/products/spinnaker-sdk/>`_ with the PySpin wrapper.
In order to use this device, both the SDK and the python wrapper must be installed.

.. autosummary::
   labscript_devices.SpinnakerCamera.labscript_devices
   labscript_devices.SpinnakerCamera.blacs_tabs
   labscript_devices.SpinnakerCamera.blacs_workers

Installation
~~~~~~~~~~~~

First ensure that the Spinnaker SDK is installed. 

The python wrapper is available via FLIR.
It must be installed separately and pointed to the correct conda environment during install.

For GigE cameras, ensure that the network interface card (NIC) on the computer with the BLACS controlling the camera has enabled Jumbo Frames.
The maximum allowed value (typically 9000) is preferable to avoid dropped frames.

Usage
~~~~~

Like the :doc:`IMAQdxCamera <IMAQdx>` device, the bulk of camera configuration is performed using a dictionary of kwargs, where the key names and values mirror those provided by the Spinnaker SDK interface.
Which parameters can/need to be set depend on the communication interface.
Discovery of what parameters are available can be done in three ways:

1. Careful reading of the Spinnaker SDK docs.
2. Mirroring the SpinView parameter names and values.
3. Connecting to the camera with a minimal configuration, viewing the current parameters dictionary, and copying the relevant values to the connection table (preferred).

Below is a generic configuration.

.. code-block:: python

   from labscript import *
   
   from labscript_devices.SpinnakerCamera.labscript_devices import SpinnakerCamera

   CCT_global_camera_attributes = {
      'AnalogControl::GainAuto': 'Off',
      'AnalogControl::Gain': 0.0,
      'AnalogControl::BlackLevelEnabled': True,
      'AnalogControl::BlackLevel': 0.0,
      'AnalogControl::GammaEnabled': False,
      'AnalogControl::SharpnessEnabled': False,
      'ImageFormatControl::Width': 1008,
      'ImageFormatControl::Height': 800,
      'ImageFormatControl::OffsetX': 200,
      'ImageFormatControl::OffsetY': 224,
      'ImageFormatControl::PixelFormat': 'Mono16',
      'ImageFormatControl::VideoMode': 'Mode0',
      'AcquisitionControl::TriggerMode': 'Off',
      'AcquisitionControl::TriggerSource': 'Line0',
      'AcquisitionControl::TriggerSelector': 'ExposureActive',
      'AcquisitionControl::TriggerActivation': 'FallingEdge',
    }
   CCT_manual_mode_attributes = {
      'AcquisitionControl::TriggerMode': 'Off',
      'AcquisitionControl::ExposureMode': 'Timed',
   }
   CCT_buffered_mode_attributes = {
      'AcquisitionControl::TriggerMode': 'On',
      'AcquisitionControl::ExposureMode': 'TriggerWidth',
   }

   SpinnakerCamera('gigeCamera',parent_device=parent,connection=conn,
               serial_number=1234567, # set to the camera serial number
               minimum_recovery_time=36e-6, # the minimum exposure time depends on the camera model & configuration
               trigger_edge_type='falling',
               camera_attributs={**CCT_global_camera_attributes,
                                 **CCT_buffered_mode_attributes},
               manual_camera_attributes={**CCT_global_camera_attributes,
                                         **CCT_manual_mode_attributes})

   start()

   gigeCamera.expose(t=0.5,'exposure1',trigger_duration=0.25)


   stop(1)


Detailed Documentation
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: labscript_devices.SpinnakerCamera
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.SpinnakerCamera.labscript_devices
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.SpinnakerCamera.blacs_tabs
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.SpinnakerCamera.blacs_workers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:
