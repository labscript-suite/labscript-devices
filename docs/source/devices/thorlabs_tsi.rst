Thorlabs Scientific Cameras
===========================

This device controls Thorlabs scientific cameras (the Zelux, Kiralux and Quantalux models) with the
`Thorlabs camera SDK <https://www.thorlabs.com/software_pages/ViewSoftwarePage.cfm?Code=ThorCam>`_ and its
``thorlabs_tsi_sdk`` Python package. It has been used with the Kiralux CS505MU.

.. autosummary::
   labscript_devices.ThorlabsTSICamera.labscript_devices
   labscript_devices.ThorlabsTSICamera.blacs_tabs
   labscript_devices.ThorlabsTSICamera.blacs_workers

Installation
~~~~~~~~~~~~

The device requires Thorlabs camera SDK 2.3 or later, which contains version 1.2.0 of the ``thorlabs_tsi_sdk``
package. BLACS reports an error if an earlier version is installed. The package is not on PyPI. It is in the SDK
download on the `ThorCam software page <https://www.thorlabs.com/software_pages/ViewSoftwarePage.cfm?Code=ThorCam>`_,
under "Programming Interfaces". The download requires a web browser; a direct link to the file does not work. The
package includes the SDK's native libraries for Linux and Windows.

Linux
-----

Download "Linux SDK and Doc. for Compact Scientific Cameras". With the Python environment of the labscript suite
active:

.. code-block:: bash

   unzip scientific_camera_interfaces-linux-*.zip
   cd Scientific_Camera_Interfaces
   sudo cp usb.rules /etc/udev/rules.d/99-thorlabs-tsi.rules
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   pip install SDK/Python_Toolkit/thorlabs_tsi_camera_python_sdk_package.zip

The udev rules give users access to the camera. The libraries require version ``GLIBCXX_3.4.25`` or later of
``libstdc++``.

Windows
-------

Install ThorCam, which installs the camera drivers, and download the Windows SDK from the same page. With the
Python environment of the labscript suite active, install the package from the SDK:

.. code-block:: bash

   pip install "SDK\Python Toolkit\thorlabs_tsi_camera_python_sdk_package.zip"

Usage
~~~~~

Like the :doc:`TriggerableCamera <triggerablecamera>` device, the camera is configured with a dictionary of attributes. The
serial number is the decimal number printed on the camera and shown by ThorCam.

.. code-block:: python

   from labscript import *

   from labscript_devices.ThorlabsTSICamera.labscript_devices import ThorlabsTSICamera

   ThorlabsTSICamera(
       'camera',
       parent_device=digital_out_device,
       connection='port0/line0',
       serial_number=34706,
       pixel_size=[3.45, 3.45],
       trigger_duration=1e-3,
       camera_attributes={
           'exposure_time_us': 1000,
           'gain': 0,
           'roi': (0, 0, 2447, 2047),
           'binx': 1,
           'biny': 1,
           'bulb_mode': False,
       },
   )

   start()
   camera.expose(t=0.5, name='atoms')
   stop(1)

The attributes are properties of the SDK's ``TLCamera`` class, with the same names and meanings, and
``bulb_mode``:

* ``simple``: ``exposure_time_us``, ``gain``, ``roi`` (``(x0, y0, x1, y1)``, inclusive), ``binx``, ``biny`` and
  ``bulb_mode``
* ``intermediate``: also ``black_level``, ``data_rate`` (``'FPS_30'`` or ``'FPS_50'``),
  ``is_frame_rate_control_enabled``, ``frame_rate_control_value`` and ``is_led_on``
* ``advanced``: also ``is_hot_pixel_correction_enabled``, ``hot_pixel_correction_threshold`` and
  ``is_eep_enabled``

Attributes that the camera model does not support are left out. The ROI is in unbinned pixels, and the camera
rounds it to pixel multiples that depend on the binning; the saved attributes have the ROI that the camera uses.
With ``bulb_mode`` true, the exposure lasts for the duration of the trigger pulse and ``exposure_time_us`` is not
used during shots. In manual mode, the camera is triggered by software.

The camera starts an exposure on the edge of the trigger pulse given by ``trigger_edge_type``, which is
``'rising'`` by default. The camera is programmed to expect this edge, so ``trigger_edge_type`` is the only setting
of the trigger polarity.

The camera stays armed between shots unless an attribute changes. Frames acquired between shots are discarded at
the start of the next shot. The camera is armed with an image buffer per exposure of the shot, and with at least 16
buffers. The number of buffers increases when a shot has more exposures than the camera has buffers, and does not
decrease. If the camera drops a frame during a shot, the images before the dropped frame are saved, and the shot
fails if ``exception_on_failed_shot`` is true.

One process per camera
~~~~~~~~~~~~~~~~~~~~~~

Only one process at a time can use a camera. While BLACS has the camera open, it holds a lock on the file
``thorlabs-tsi-camera-<serial number>.lock`` in the temporary directory (:func:`tempfile.gettempdir`), and a
second process that opens the camera with this device gets an error instead. The operating system releases the
lock when the process exits, however it exits. Another program that uses the camera can take the same lock with
the `filelock <https://py-filelock.readthedocs.io>`_ package, so that BLACS and the program do not use the camera
at the same time:

.. code-block:: python

   import tempfile
   from pathlib import Path
   from filelock import FileLock

   lock = FileLock(Path(tempfile.gettempdir()) / 'thorlabs-tsi-camera-34706.lock', thread_local=False)
   lock.acquire(timeout=0)  # Raises filelock.Timeout if BLACS has the camera open

On Windows, the temporary directory is different for each user, so the lock only excludes processes of the same
user.

The SDK is opened once in each worker process and closed when the worker shuts down. Restarting the BLACS tab
starts a new worker process.
