Triggerable Cameras
===================

Overview
~~~~~~~~

The generic camera, from which all the others derive. It holds the structure
every camera shares -- exposures, triggering, camera attributes, and where
images are stored in the shot file -- and knows nothing about any particular
camera API. A camera for a given API is a subclass of this whose BLACS worker
names an interface class.

That interface class is the object the worker talks to in place of hardware,
and :obj:`~labscript_devices.TriggerableCamera.blacs_workers.TriggerableCameraInterface`
is what it implements: the contract the worker calls, an acquisition loop, and
an abort. A camera should inherit it; a member it has not written then raises
an error naming that member, rather than an AttributeError. A camera that does
not must write every member the worker calls; a worker subclassing
:obj:`~labscript_devices.IMAQdxCamera.blacs_workers.IMAQdxCameraWorker` still
reads such a camera's attributes one at a time, but that route is deprecated.

.. autosummary::
   labscript_devices.TriggerableCamera.labscript_devices
   labscript_devices.TriggerableCamera.blacs_tabs
   labscript_devices.TriggerableCamera.blacs_workers

Installation
~~~~~~~~~~~~


Usage
~~~~~


Detailed Documentation
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: labscript_devices.TriggerableCamera
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.TriggerableCamera.labscript_devices
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.TriggerableCamera.blacs_tabs
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.TriggerableCamera.blacs_workers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:
