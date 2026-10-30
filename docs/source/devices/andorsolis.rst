Andor Solis Cameras
===================

A labscript device for controlling Andor scientific cameras via the Andor SDK (SDK2) interface.

Presently, this device is hard-coded for use with the iXon camera.
Minor modifications can allow use with other Andor cameras, so long as they are compatible with the Andor SDK2 library.

.. autosummary::
   labscript_devices.AndorSolis.labscript_devices
   labscript_devices.AndorSolis.blacs_tabs
   labscript_devices.AndorSolis.blacs_workers

Installation
~~~~~~~~~~~~

The Andor SDK is available from Andor as a paid product (typically purchased with the camera).
The device runs only on Windows. It loads the SDK library ``atmcd64d.dll`` from
``C:\Program Files\Andor SOLIS\Drivers``.

Detailed Documentation
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: labscript_devices.AndorSolis
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.AndorSolis.labscript_devices
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.AndorSolis.blacs_tabs
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.AndorSolis.blacs_workers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members: