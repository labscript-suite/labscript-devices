Dummy Camera
============

Overview
~~~~~~~~

A camera with no hardware behind it, whose images come from a function you
write. Each exposure names a function of the camera's pixels; the function is
evaluated while the shot compiles, where the shot's globals are in scope, and
the images it returns are stored in the shot file. BLACS then acquires them
through the path every camera's images take, so BLACS displays them and a lyse
script reads them exactly as it reads a real camera's.

.. autosummary::
   labscript_devices.DummyCamera.labscript_devices
   labscript_devices.DummyCamera.sensor
   labscript_devices.DummyCamera.blacs_tabs
   labscript_devices.DummyCamera.blacs_workers

Installation
~~~~~~~~~~~~

No installation and no hardware. Add it to a connection table as you would any
camera. It has no sensor to fall back on, so its :code:`camera_attributes` must
give it a :code:`Width` and a :code:`Height`: an image quietly the wrong size is
worse than one that does not compile.

Usage
~~~~~

An image function is passed to :code:`expose` by keyword. It takes the camera's
coordinate grid, then whatever else you choose to pass it, and returns an array
of counts of the same shape as the grid, which the camera clips to what one of
its pixels holds and stores as :code:`uint16`, the way a real camera reads out. :code:`X` and :code:`Y` are in object-plane micrometres, scaled by the
camera's :code:`pixel_size` and :code:`magnification`, so a function describes a
cloud in microns rather than in pixels.

.. code-block:: python

    DummyCamera(
        'camera',
        camera_trigger,
        'trigger',
        orientation='side',
        trigger_duration=0.01,
        pixel_size=[5.2, 5.2],
        magnification=2.0,
        camera_attributes={'Width': 512, 'Height': 512, 'PixelFormat': 'Mono16'},
    )

    def absorption_frame(X, Y, atoms):
        """A probe beam, with a cloud absorbed out of it when atoms is True.

        `atom_number` and `cloud_radius` are globals of the shot. Nothing
        passes them in: they are in scope by the time this is called, because
        it is called while the shot compiles.
        """
        probe = 8000.0 * np.exp(-(X ** 2 + Y ** 2) / (2 * 400.0 ** 2))
        if not atoms:
            return probe
        peak_density = atom_number / (2 * np.pi * cloud_radius ** 2)
        column_density = peak_density * np.exp(
            -(X ** 2 + Y ** 2) / (2 * cloud_radius ** 2)
        )
        return probe * np.exp(-0.2907 * column_density)

    start()
    camera.expose(1.0, 'absorption', 'atoms', function=absorption_frame, atoms=True)
    camera.expose(1.1, 'absorption', 'probe', function=absorption_frame, atoms=False)
    camera.expose(1.2, 'absorption', 'dark', function=lambda X, Y: np.zeros(X.shape))
    stop(2)

The three frames of an absorption image come from one function called three
ways. Sharing the function is what makes them agree with each other: the probe
beam is identical in the atoms and probe frames, so an optical density computed
from them means something. A working version of this is in
:code:`labscript_devices/DummyCamera/testing/test.py`.

The function is called once per exposure as the shot compiles, and is never
stored anywhere -- only the images it returns are. So it can be any callable,
including a local function or a lambda, and the machine BLACS runs on does not
need it, even when the camera's worker is on another host.

An exposure given no function gets :obj:`~labscript_devices.DummyCamera.sensor.blank_image`:
a real frame, of nothing, at the size the sensor is configured for. That is also
what the Snap button in the BLACS tab shows, where there is no shot and so no
function at all. The camera invents nothing on its own account -- anything in a
frame got there because a function you wrote put it there.

Noise is the function's business too: the camera adds none. What the camera does add
is a :code:`NOT_REAL_DATA` attribute beside the images in the shot file, which is
what marks them as simulated. It is an attribute rather than a watermark drawn
onto the pixels because a watermark does not cancel in
:code:`OD = -log((atoms - dark) / (probe - dark))`, and would ruin the analysis
this camera exists to feed.

Detailed Documentation
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: labscript_devices.DummyCamera
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.DummyCamera.labscript_devices
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.DummyCamera.sensor
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
