Dummy Pseudoclock
=================

This device represents a dummy labscript device for purposes of testing BLACS
and labscript. The device is a PseudoclockDevice, and can be the sole device
in a connection table or experiment.

.. autosummary::
   labscript_devices.DummyPseudoclock.labscript_devices
   labscript_devices.DummyPseudoclock.blacs_tabs
   labscript_devices.DummyPseudoclock.blacs_workers
   labscript_devices.DummyPseudoclock.runviewer_parsers

Usage
~~~~~

.. code-block:: python

	from labscript import *

	from labscript_devices.DummyPseudoclock.labscript_devices import DummyPseudoclock
	from labscript_devices.DummyIntermediateDevice.labscript_devices import DummyIntermediateDevice

	DummyPseudoclock(name='dummy_clock',BLACS_connection='dummy')
	DummyIntermediateDevice(name='dummy_device',BLACS_connection='dummy2',
							parent_device=dummy_clock.clockline)

	DigitalOut('do0', dummy_device, 'do0')
	AnalogOut('ao0', dummy_device, 'ao0')

	start()
	do0.go_high(0.1)
	ao0.ramp(t=0.2, duration=0.5, initial=0, final=1, samplerate=1e3)
	stop(1)


Detailed Documentation
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: labscript_devices.DummyPseudoclock.labscript_devices
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.DummyPseudoclock.blacs_tabs
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.DummyPseudoclock.blacs_workers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.DummyPseudoclock.runviewer_parsers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:
