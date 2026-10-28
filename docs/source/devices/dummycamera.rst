Dummy Camera
============

A :doc:`triggerable camera <triggerablecamera>` without hardware, the images of which are
computed when the shot is compiled. BLACS saves them to the shot file after the shot as it
saves the images of a camera, so that an experiment and its analysis can be run without the
camera.

.. autosummary::
   labscript_devices.DummyCamera.labscript_devices
   labscript_devices.DummyCamera.blacs_tabs
   labscript_devices.DummyCamera.blacs_workers

Usage
~~~~~

Each exposure takes a function, which is called during compilation as
``function(X, Y, **kwargs)`` with the keyword arguments of the exposure. ``X`` and ``Y`` are
the coordinates of the pixels in the object plane, in micrometres from the centre of the
image. The function returns the image as an array of the same shape, in counts. The camera's
``camera_attributes`` give the size of the images, and the pixel format, which sets the
saturation level.

.. code-block:: python

   import numpy as np
   from labscript import *

   from labscript_devices.DummyCamera.labscript_devices import DummyCamera

   DummyCamera(
       'camera',
       parent_device=digital_out_device,
       connection='port0/line0',
       orientation='side',
       pixel_size=[5.0, 5.0],
       magnification=2.0,
       trigger_duration=1e-3,
       camera_attributes={'Width': 256, 'Height': 192, 'PixelFormat': 'Mono12'},
   )

   def absorption_image(X, Y, atoms, probe=3000, dark=100):
       optical_depth = 2 * atoms * np.exp(-(X**2 + Y**2) / (2 * 50**2))
       return dark + probe * np.exp(-optical_depth)

   start()
   camera.expose(0.5, 'absorption', 'atoms', function=absorption_image, atoms=True)
   camera.expose(0.6, 'absorption', 'probe', function=absorption_image, atoms=False)
   camera.expose(0.7, 'absorption', 'dark', function=lambda X, Y: np.full(X.shape, 100))
   stop(1)

The images are stored in the dataset ``devices/<name>/IMAGES`` of the shot file, in the
order of the exposure times. The function itself is not stored, so it can be any callable.
In manual mode, the camera returns images of zeros.

The attribute ``mock_data`` of the image group is true for the images of a ``DummyCamera``.

Detailed Documentation
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: labscript_devices.DummyCamera.labscript_devices
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.DummyCamera.blacs_tabs
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.DummyCamera.blacs_workers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:
