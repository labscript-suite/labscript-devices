Triggerable Cameras
===================

Every camera device is a subclass of :obj:`TriggerableCamera
<labscript_devices.common.triggerable_camera.labscript_devices.TriggerableCamera>`, which is
triggered by a digital output and saves its images to the shot file. Its BLACS tab displays
the images, and in manual mode acquires single frames (Snap) or acquires continuously, shows
the camera's attributes, and subtracts a background image. A camera device class adds only
the code that communicates with its camera. ``TriggerableCamera`` is not itself a device that
a connection table can use.

.. autosummary::
   labscript_devices.common.triggerable_camera.labscript_devices
   labscript_devices.common.triggerable_camera.blacs_tabs
   labscript_devices.common.triggerable_camera.blacs_workers

Usage
~~~~~

A camera's constructor arguments are those of :obj:`TriggerableCamera
<labscript_devices.common.triggerable_camera.labscript_devices.TriggerableCamera>`, and the
pages of the camera devices list any differences. The camera is configured with a dictionary
of attributes, ``camera_attributes``, the names and values of which are those of the camera's
programming interface. The Attributes button of the BLACS tab shows the camera's current
attributes as a dictionary that can be copied into the connection table.

.. code-block:: python

   from labscript import *

   from labscript_devices.IMAQdxCamera.labscript_devices import IMAQdxCamera

   IMAQdxCamera(
       'camera',
       parent_device=digital_out_device,
       connection='port0/line0',
       serial_number=0xDEADBEEF,
       orientation='side',
       trigger_duration=1e-3,
       camera_attributes={...},
   )

   start()
   camera.expose(t=0.5, name='absorption', frametype='atoms')
   camera.expose(t=0.6, name='absorption', frametype='probe')
   stop(1)

``mock=True`` replaces the camera with one that returns an image of a Gaussian dip with
Poisson noise and the text "NOT REAL DATA", so that a connection table and experiment can be
run without the camera.

Shot file
~~~~~~~~~

The exposures are in the dataset ``devices/<name>/EXPOSURES``, with the time, name, frame type
and trigger duration of each. After the shot, the images are saved in
``images/<orientation>/<name>/<frametype>``, or ``images/<device name>/<name>/<frametype>``
if the camera has no orientation, as ``uint16`` datasets. Several images with the same name and
frame type are saved as one three-dimensional dataset. The group ``images/<orientation>`` has
the attributes ``camera``, the device name, ``failed_shot``, which is true if fewer images
were acquired than requested, and ``mock_data``, which is true if the images were generated rather
than acquired by a camera, as those of the mock camera are. It also has the camera's attributes at the visibility level given by
``saved_attribute_visibility_level``. lyse includes the attributes of the group in its
dataframe, so analysis routines can read ``mock_data`` from the column
``(<orientation>, 'mock_data')``.

Adding a camera
~~~~~~~~~~~~~~~

A camera device has the device class, BLACS tab and BLACS worker of the other devices:

* the device class is a subclass of :obj:`TriggerableCamera
  <labscript_devices.common.triggerable_camera.labscript_devices.TriggerableCamera>` with a
  ``description``;
* the BLACS tab is a subclass of :obj:`TriggerableCameraTab
  <labscript_devices.common.triggerable_camera.blacs_tabs.TriggerableCameraTab>` that sets
  ``worker_class`` to the worker;
* the worker is a subclass of :obj:`TriggerableCameraWorker
  <labscript_devices.common.triggerable_camera.blacs_workers.TriggerableCameraWorker>` that
  sets ``interface_class`` to a subclass of :obj:`CameraInterface
  <labscript_devices.common.triggerable_camera.blacs_workers.CameraInterface>`.

The interface class communicates with the camera, and implements the methods of
``CameraInterface`` that raise ``NotImplementedError``. It is instantiated with the serial
number; a worker for a camera that needs other arguments reimplements ``get_camera()``.
The interface class imports the camera's programming interface in its ``__init__`` method,
so that the worker module imports, and ``mock=True`` works, without it. The
:doc:`IMAQdx <IMAQdx>` and :doc:`Pylon <pylon>` devices are examples.

Detailed Documentation
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: labscript_devices.common.triggerable_camera.labscript_devices
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.common.triggerable_camera.blacs_tabs
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.common.triggerable_camera.blacs_workers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:
