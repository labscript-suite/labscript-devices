GenICam Cameras
===============

A :doc:`triggerable camera <triggerablecamera>` for GigE Vision and USB3 Vision cameras,
controlled through a GenTL producer with the `harvesters
<https://github.com/genicam/harvesters>`_ package. A GenTL producer is a library, with the
extension ``.cti``, that the camera's manufacturer supplies with its software, for example
Basler pylon, FLIR Spinnaker, Allied Vision Vimba X or MATRIX VISION mvGenTL Acquire.
Neither NI software nor the manufacturer's Python package is needed.

.. autosummary::
   labscript_devices.GenICamCamera.labscript_devices
   labscript_devices.GenICamCamera.blacs_tabs
   labscript_devices.GenICamCamera.blacs_workers

Installation
~~~~~~~~~~~~

Install harvesters, which installs the ``genicam`` package, in the Python environment of
the labscript suite on the computer that runs the BLACS worker:

.. code-block:: bash

   pip install harvesters

Neither package is available from conda. Then install the manufacturer's software, which
contains the GenTL producer. The installer normally adds the directory of the producer to
the ``GENICAM_GENTL64_PATH`` environment variable, where the device finds it. Otherwise, give
the path of the ``.cti`` file as ``cti_file``.

Usage
~~~~~

The attributes are GenICam features, with the names of the GenICam Standard Features Naming
Convention, such as ``ExposureTime``, ``Gain``, ``PixelFormat``, ``Width`` and ``Height``. The
visibility levels ``'simple'``, ``'intermediate'`` and ``'advanced'`` are the GenICam
visibilities Beginner, Expert and Guru. The pixel format must be ``Mono8``, ``Mono10``,
``Mono12``, ``Mono14`` or ``Mono16``.

For hardware triggering, the camera is configured with ``TriggerMode``, ``TriggerSource`` and
``TriggerActivation``. With ``manual_mode_camera_attributes``, the camera can run without a
trigger in manual mode:

.. fragment

.. code-block:: python

   from labscript import *

   from labscript_devices.GenICamCamera.labscript_devices import GenICamCamera

   GenICamCamera(
       'camera',
       parent_device=digital_out_device,
       connection='port0/line0',
       serial_number='40123456',
       trigger_duration=1e-3,
       camera_attributes={
           'PixelFormat': 'Mono12',
           'ExposureTime': 1000.0,
           'TriggerSelector': 'FrameStart',
           'TriggerMode': 'On',
           'TriggerSource': 'Line1',
           'TriggerActivation': 'RisingEdge',
       },
       manual_mode_camera_attributes={'TriggerMode': 'Off'},
   )

   start()
   camera.expose(t=0.5, name='atoms')
   stop(1)

The serial number is a string, as the producer reports it. If no camera has the serial
number, the error message lists the serial numbers of the cameras that the producer found.

Detailed Documentation
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: labscript_devices.GenICamCamera.labscript_devices
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.GenICamCamera.blacs_tabs
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.GenICamCamera.blacs_workers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:
