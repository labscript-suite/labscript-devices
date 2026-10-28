IMAQdx Cameras
==============

Overview
~~~~~~~~

A camera controlled through NI-IMAQdx, which supports GigE Vision, USB3 Vision and IEEE 1394
cameras. It is a :doc:`triggerable camera <triggerablecamera>`.

.. autosummary::
   labscript_devices.IMAQdxCamera.labscript_devices
   labscript_devices.IMAQdxCamera.blacs_tabs
   labscript_devices.IMAQdxCamera.blacs_workers

Installation
~~~~~~~~~~~~

The camera is controlled through the NI-IMAQdx driver, which is installed by NI Vision
Acquisition Software. labscript-devices calls the driver's libraries directly and needs
no Python package for it. NI-IMAQdx needs a licence for each computer, and stops working
30 days after installation if it has not been activated.


Usage
~~~~~

The camera is configured as described for :doc:`triggerable cameras <triggerablecamera>`,
and the attributes are those shown by NI MAX. A serial number given as a string is
hexadecimal. Attributes that the connection table does not set keep the values that are
saved in NI MAX; attributes set by BLACS are not saved in the camera.


Detailed Documentation
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: labscript_devices.IMAQdxCamera
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.IMAQdxCamera.labscript_devices
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.IMAQdxCamera.blacs_tabs
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.IMAQdxCamera.blacs_workers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:
