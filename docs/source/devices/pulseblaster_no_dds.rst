Pulseblaster (-DDS)
===================

Overview
~~~~~~~~

This labscript device controls the Spincore Pulseblasers that do not have DDS outputs.
The Pulseblaster is a programmable pulse generator that is the typical timing backbone of an experiment (ie it generates the pseudoclock timing pulses that control execution of other devices in the experiment).
This labscript device inherits from the :doc:`Pulseblaster <pulseblaster>` device.
The primary difference is the removal of code handling DDS outputs.

The labscript-suite currently supports a number of no-dds variants of the Pulseblaster device, each with different numbers of outputs and clock frequencies:

 * `PulseBlaster_No_DDS`: Has 24 digital outputs and a 100 MHz core clock frequency.
 * `PulseBlasterUSB`: Identical to the `PulseBlaster_No_DDS` device
 * `PulseBlaster_SP2_24_100_32k`: Has slightly lower `clock_limit` and `clock_resolution` than the standard device. Also supports 32k instructions instead of the standard 4k.
 * `PulseBlasterESRPro200`: Has a 200 MHz core clock frequency.
 * `PulseBlasterESRPro500`: Has a 500 MHz core clock frequency and 24 flags.

ESR-Pro PulseBlasters
^^^^^^^^^^^^^^^^^^^^^

The timing resolution of a normal PulseBlaster is one clock cycle, the minimum interval is typically limited to 5 clock cycles (or nine in the case of the external memory models like the 32k).
The ESR-Pro series of PulseBlasters have the Short Pulse Feature, which allows for pulse lengths of 1-5 clock periods. This is controlled using the top three bits (21-23) according to the following table.

.. csv-table:: Short Pulse Control
	:header: "SpinAPI Define", "Bits 21-23", "Clock Periods", "Pulse Length (ns) at 500 MHz" 
	:widths: auto
	:align: center

	\- , 000, \- , "All outputs low"
	"ONE_PERIOD", 001, 1, 2
	"TWO_PERIOD", 010, 2, 4
	"THREE_PERIOD", 011, 3, 6
	"FOUR_PERIOD", 100, 4, 8
	"FIVE_PERIOD", 101, 5, 10
	"ON", 111, \- , "Short Pulse Disabled"

Currently, the PulseBlaster labscript device does not use this functionality.
However, in order to get any output at all, bits 21-23 must be set high manually.
`PulseBlasterESRPro500` exposes all 24 flags so that flags 21-23 can be set high from the connection table or the BLACS front panel.


Installation
~~~~~~~~~~~~

Use of the Pulseblaster requires driver installation available from the manufacturer `here <https://www.spincore.com/support/>`_.
The corresponding python wrapper, `spinapi <https://github.com/chrisjbillington/spinapi/>`_, is a dependency of labscript-devices and is installed with it.

Usage
~~~~~

.. code-block:: python

	from labscript import *

	from labscript_devices.PulseBlaster_No_DDS.labscript_devices import PulseBlaster_No_DDS

	PulseBlaster_No_DDS(name='pb', board_number=0, programming_scheme='pb_start/BRANCH')

	ClockLine(name='pb_clockline_fast', pseudoclock=pb.pseudoclock, connection='flag 0')
	ClockLine(name='pb_clockline_slow', pseudoclock=pb.pseudoclock, connection='flag 1')

	DigitalOut(name='pb_0', parent_device=pb.direct_outputs, connection='flag 2')

	start()

	stop(1)

Detailed Documentation
~~~~~~~~~~~~~~~~~~~~~~

.. autosummary::
	labscript_devices.PulseBlaster_No_DDS
	labscript_devices.PulseBlasterUSB
	labscript_devices.PulseBlaster_SP2_24_100_32k
	labscript_devices.PulseBlasterESRPro200
	labscript_devices.PulseBlasterESRPro500

PulseBlaster_No_DDS
^^^^^^^^^^^^^^^^^^^

.. automodule:: labscript_devices.PulseBlaster_No_DDS.labscript_devices
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.PulseBlaster_No_DDS.blacs_tabs
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.PulseBlaster_No_DDS.blacs_workers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.PulseBlaster_No_DDS.runviewer_parsers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

PulseBlasterUSB
^^^^^^^^^^^^^^^

.. automodule:: labscript_devices.PulseBlasterUSB.labscript_devices
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.PulseBlasterUSB.blacs_tabs
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.PulseBlasterUSB.blacs_workers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.PulseBlasterUSB.runviewer_parsers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

PulseBlaster_SP2_24_100_32k
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. automodule:: labscript_devices.PulseBlaster_SP2_24_100_32k.labscript_devices
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.PulseBlaster_SP2_24_100_32k.blacs_tabs
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.PulseBlaster_SP2_24_100_32k.blacs_workers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.PulseBlaster_SP2_24_100_32k.runviewer_parsers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

PulseBlasterESRPro200
^^^^^^^^^^^^^^^^^^^^^

.. automodule:: labscript_devices.PulseBlasterESRPro200.labscript_devices
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.PulseBlasterESRPro200.blacs_tabs
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.PulseBlasterESRPro200.blacs_workers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.PulseBlasterESRPro200.runviewer_parsers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

PulseBlasterESRPro500
^^^^^^^^^^^^^^^^^^^^^

.. automodule:: labscript_devices.PulseBlasterESRPro500.labscript_devices
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.PulseBlasterESRPro500.blacs_tabs
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.PulseBlasterESRPro500.blacs_workers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.PulseBlasterESRPro500.runviewer_parsers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members: