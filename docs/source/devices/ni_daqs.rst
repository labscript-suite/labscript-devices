NI DAQs
=======

Overview
~~~~~~~~

This labscript device is a master device that can control a wide range of NI Multi-function data acquistion devices.

Installation
~~~~~~~~~~~~

This labscript device requires an installation of the NI-DAQmx module, available for free from `NI <https://www.ni.com/en-us/support/downloads/drivers/download.ni-daqmx.html>`_.

The python bindings are provided by the PyDAQmx package, available through pip.


Adding a Device
~~~~~~~~~~~~~~~

While the `NI_DAQmx` device can be used directly by manually specifying the many necessary parameters, 
it is preferable to add the device via an appropriate subclass. 
This process is greatly simplified by using the :mod:`get_capabilities.py <labscript_devices.NI_DAQmx.models.get_capabilities>` script
followed by the :mod:`generate_subclasses.py <labscript_devices.NI_DAQmx.models.generate_subclasses>` script.

To add support for a DAQmx device that is not yet supported, run `get_capabilities.py` on
a computer with the device in question connected (or with a simulated device of the
correct model configured in NI-MAX). This will introspect the capabilities of the device
and add those details to `capabilities.json`. To generate labscript device classes for all
devices whose capabilities are known, run `generate_subclasses.py`. Subclasses of NI_DAQmx
will be made in the `models` subfolder, and they can then be imported into labscript code with:

.. code-block:: python

	from labscript_devices.NI_DAQmx.labscript_devices import NI_PCIe_6363

or similar. The class naming is based on the model name by prepending "NI\_" and
replacing the hyphen with an underscore, i.e. 'PCIe-6363' -> NI_PCIe_6363.

Generating device classes requires the Python code-formatting library 'black', which can
be installed via pip (Python 3.6+ only). If you don't want to install this library, the
generation code will still work, it just won't be formatted well.

The current list of pre-subclassed devices is:

.. toctree::
	:maxdepth: 2

	ni_daq_models


Usage
~~~~~

NI Multifunction DAQs generally provide hardware channels for 
:class:`StaticAnalogOut <labscript:labscript.labscript.StaticAnalogOut>`,
:class:`StaticDigitalOut <labscript:labscript.labscript.StaticDigitalOut>`,
:class:`AnalogOut <labscript:labscript.labscript.AnalogOut>`,
:class:`DigitalOut <labscript:labscript.labscript.DigitalOut>`,
and :class:`AnalogIn <labscript:labscript.labscript.AnalogIn>` labscript quantities for use in experiments.
Exact numbers of channels, performance, and configuration depend on the model of DAQ used.

.. code-block:: python

	from labscript import *

	from labscript_devices.DummyPseudoclock.labscript_devices import DummyPseudoclock
	from labscript_devices.NI_DAQmx.models.NI_USB_6343 import NI_USB_6343

	DummyPseudoclock('dummy_clock',BLACS_connection='dummy')

	NI_USB_6343(name='daq',parent_device=dummy_clock.clockline,
				MAX_name='ni_usb_6343',
				clock_terminal='/ni_usb_6343/PFI0',
				acquisition_rate=100e3)

	AnalogIn('daq_ai0',daq,'ai0')
	AnalogIn('daq_ai1',daq,'ai1')

	AnalogOut('daq_ao0',daq,'ao0')
	AnalogIn('daq_ai1',daq,'ai1')

WaitMonitors
------------

NI DAQs are also used within labscript to provide a :class:`WaitMonitor <labscript:labscript.labscript.waitmonitor>`.
When configured, the `WaitMonitor` allows for arbitrary-length pauses in experiment execution, waiting for some trigger to restart.
The monitor provides a measurement of the duration of the wait for use in interpreting the resulting data from the experiment.

Configuration uses three digital I/O connections on the DAQ:

* The parent_connection which sends pulses at the beginning of the experiment, the start of the wait, and the end of the wait.
* The acquisition_connection which must be wired to a counter and measures the time between the pulses of the parent connection.
* The timeout_connection which can send a restart pulse if the wait times out.

An example configuration of a `WaitMonitor` using a NI DAQ is shown here

.. code-block:: python

	# A wait monitor for AC-line triggering
	# This requires custom hardware
	WaitMonitor(name='wait_monitor',parent_device=daq,connection='port0/line0',
				acquisition_device=daq, acquisition_connection='ctr0',
				timeout_device=daq, timeout_connection='PFI1')
	# Necessary to ensure even number of digital out lines in shot
	DigitalOut('daq_do1',daq,'port0/line1')

Note that the counter connection is specified using the logical label `'ctr0'`. On many NI DAQs, the physical connection to this counter is PFI9.
The physical wiring for this configuration would have port0/line0 wired directly to PFI9, with PFI1 being sent to the master pseudoclock retriggering system in case of timeout.
If timeouts are not expected/represent experiment failure, this physical connection can be omitted.

In addition to their external ports, some types of NI DAQ modules (PXI, PXIe, CompactDAQ) feature internal ports, known as "terminals" in NI terminology.
Terminals include most clocks and triggers in a module, as well as the external PFIN connections.
The buffered and static digital IO connections are not terminals.
Connections between terminals can be used for sharing clocks or triggers between modules in the same chassis (note: if sufficient clocklines and external inputs are available, it is likely preferable to simply use a unique clockline for each card).
Within labscript, there are two methods for accessing this functionality.
For sharing the clock input signal to other cards, the `clock_mirror_terminal` argument in the constructor can be specified. For example, in a system with two PXI-6733 analog cards in a PXI chassis (which supports 8 internal triggers, named `PXI_TrigN`), the connection table entries are

.. code-block:: python

	NI_PXI_6733(name='dev_1',
				...,
				clock_terminal='/Dev1/PFI0',
				clock_mirror_terminal='/Dev1/PXI_Trig0',
				MAX_name='Dev1')

	NI_PXI_6733(name='dev_2',
				...,
				clock_terminal='/Dev2/PXI_Trig0',
				MAX_name='Dev2')

However, some NI DAQ modules can not be clocked from certain terminal.
To determine this, consult the `Device Routes` tab in NI MAX.
If there is not a `Direct Route` or `Indirect Route` between the clock source and clock destination, the best option is to choose a different `clock_mirror_terminal` if possible.
For some combinations of modules, there will be no pair of triggers linked to all the cards.
To handle this situation, two triggers can be linked using the `connected_terminals` argument.
This argument takes a list of tuples of terminal names, and connects the first terminal to the second terminal.
For example, to share the clock in the previous with an additional PXIe-6535 digital card (which can not use `PXI_Trig0` as a clock), the connection table entries are

.. code-block:: python

	NI_PXI_6733(name='dev_1',
				...,
				clock_terminal='/Dev1/PFI0',
				clock_mirror_terminal='/Dev1/PXI_Trig0',
				MAX_name='Dev1')

	NI_PXI_6733(name='dev_2',
				...,
				clock_terminal='/Dev2/PXI_Trig0',
				MAX_name='Dev2')

	NI_PXIe_6535(name='dev_3',
				...,
				clock_terminal='/Dev3/PXI_Trig7',
				MAX_name='Dev3',
				connected_terminals=[('/Dev3/PXI_Trig0', '/Dev3/PXI_Trig7')])

In addition to clocking, the `connected_terminals` argument can be used to link output terminals on an NI DAQ module to shared triggers, then link those shared triggers to input terminals of another NI DAQ module in the same chassis.

AI timing skew
--------------

Given how the NI-DAQmx driver currently works,
all of the outputs (and generally other hardware) are hardware-timed via direct outputs from the parent pseudoclocks.
Under default usage, this is not true for the analog inputs of the DAQs,
which are timed via the internal reference oscillator of the DAQ.
Synchronization between the two is handled at the end by correlating start times and slicing the AI traces at the appropriate times.
This works fine if the reference clocks for the pseudoclock and the DAQ don't drift relative to each other,
but that is generally not the case for a longer shot (on the order of 1 second) since the standard clocks for a pulseblaster and a DAQ both have accuracy on the order of 50 ppm.

With version 1.2.0 of the NI-DAQmx driver, this issue can be mitigated by suppling an external sample timebase that is phase synchronous with the DAQ's pseudoclock device.
This is done using the DAQmx `SampleClkTimebase` synchronization method.
Simply provide an external clocking signal that is faster than the analog input sampling rate,
and the DAQ will use an internall PLL to derive the AI sample clock from the provided timebase.
Specifying an externally provided sample timebase is done using the `AI_timebase_terminal` and `AI_timebase_rate` arguments,
which specify the input terminal (generally a PFI line) and the clock frequency.

Detailed Documentation
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: labscript_devices.NI_DAQmx
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.NI_DAQmx.labscript_devices
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.NI_DAQmx.blacs_tabs
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.NI_DAQmx.blacs_workers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.NI_DAQmx.runviewer_parsers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.NI_DAQmx.daqmx_utils
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.NI_DAQmx.utils
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:
