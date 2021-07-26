Pulseblaster
============

This labscript device controls the Spincore PulseblaserDDS-II-300-AWG.
The Pulseblaster is a programmable pulse generator that is the typical timing backbone of an experiment (ie it generates the pseudoclock timing pulses that control execution of other devices in the experiment).
This labscript device is the master implementation of the various Pulseblaster devices.
Other Pulseblaster labscript devices subclass this device and make the relevant changes to hard-coded values.
Most importantly, the `core_clock_freq` must be manually set to match that of the Pulseblaster being used in order for the timing of the programmed pulses to be correct (in the `labscript_device` and the `BLACS_worker`).

This particular version of Pulseblaster has a 75 MHz core clock frequency and also has DDS synthesizer outputs.

Installation
~~~~~~~~~~~~

Use of the Pulseblaster requires driver installation available from the manufacturer `here <https://www.spincore.com/support/>`_.
The corresponding python wrapper, `spinapi <https://github.com/chrisjbillington/spinapi/>`_ is available via pip.

.. code-block:: bash

	pip install -U spinapi

Usage
~~~~~

.. code-block:: python

	from labscript import *

	from labscript_devices.PulseBlaster import PulseBlaster

	PulseBlaster(name='pb',board_number=0,programming_scheme='pb_start/BRANCH')

	Clockline(name='pb_clockline_fast', pseudoclock=pb.pseudoclock,connection='flag 0')
	Clockline(name='pb_clockline_slow', pseudoclock=pb.pseudoclock,connection='flag 1')

	DigitalOut(name='pb_0',parent_device=pb.direct_outputs,connection='flag 2')

	PulseBlasterDDS(name='pb_dds_0',parent_device=pb.direct_outputs, 'channel 0')

	start()

	stop(1)

Detailed Documentation
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: labscript_devices.PulseBlaster
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members: