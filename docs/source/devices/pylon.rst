Pylon Cameras
=============

Overview
~~~~~~~~

This device allows control of Basler scientific cameras via the `Pylon API <https://docs.baslerweb.com/pylon-camera-software-suite>`_ with the `PyPylon python wrapper <https://pypi.org/project/pypylon/>`_. In order to use this device, both the Basler Pylon API and the PyPylon wrapper must be installed.

.. autosummary::
   labscript_devices.PylonCamera.labscript_devices
   labscript_devices.PylonCamera.blacs_tabs
   labscript_devices.PylonCamera.blacs_workers
   labscript_devices.PylonCamera.register_classes

Installation
~~~~~~~~~~~~

First ensure that the Basler Pylon SDK is installed. It is available for free `here <https://docs.baslerweb.com/pylon-camera-software-suite>`_ (after signing up for a free account with Basler). It is advisable to use the Pylon Viewer program that comes with the SDK to test communications with the camera.

The python wrapper is installed via pip:

.. code-block:: bash

   pip install -U pypylon

At present, the wrapper is tested and confirmed compatible with Pylon 5 for USB3 and GigE interface cameras.

For GigE cameras, ensure that the network interface card (NIC) on the computer with the BLACS controlling the camera has enabled Jumbo Frames. That maximum allowed value (typically 9000) is preferable to avoid dropped frames.

For USB3 cameras, care should be taken to use a USB3 host that is compatible with the Basler cameras. Basler maintains a list of compatible host controllers. The cameras will work on any USB3 port, but non-compatible hosts will not allow for the faster performance.

Usage
~~~~~

Like the :doc:`IMAQdxCamera <IMAQdx>` device, the bulk of camera configuration is performed using a dictionary of kwargs, where the key names and values mirror those provided by the Pylon SDK interface. Which parameters can/need to be set depend on the communication interface. Discovery of what parameters are available can be done in three ways:

1. Careful reading of the Pylon SDK docs.
2. Mirroring the Pylon Viewer parameter names and values.
3. Connecting to the camera with a minimal configuration, viewing the current parameters dictionary, and copying the relevant values to the connection table (preferred).

This is an example configuration for a GigE camera.

.. code-block:: python
   
   from labscript_devices.PylonCamera.labscript_devices import PylonCamera

   PylonCamera('gigeCamera',parent_device=parent,connection=conn,
               serial_number=1234567, # set to the camera serial number
               minimum_recovery_time=36e-6, # the minimum exposure time depends on the camera model & configuration
               camera_attributs={},
               manual_camera_attributes={})

   start()

   gigeCamera.expose(t=0.5,'exposure1')

   stop(1)

This is an example configuration for a USB3 camera.

.. code-block:: python
   
   from labscript_devices.PylonCamera.labscript_devices import PylonCamera

   PylonCamera('usb3Camera',parent_device=parent,connection=conn,
               serial_number=1234567, 
               minimum_recovery_time=36e-6, 
               camera_attributs={},
               manual_camera_attributes={})

   start()

   usb3Camera.expose(t=0.5,'exposure1')

   stop(1)



Detailed Documentation
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: labscript_devices.PylonCamera
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.PylonCamera.labscript_devices
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.PylonCamera.blacs_tabs
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.PylonCamera.blacs_workers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.PylonCamera.register_classes
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members: