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

While the `NI_DAQmx` device can be used directly by manually specifying the many necessary parameters, it is preferable to add the device via an appropriate subclass. This process is greatly simplified by using the `get_capabilities.py` script.

To add support for a DAQmx device that is not yet supported, run `get_capabilities.py` on
a computer with the device in question connected (or with a simulated device of the
correct model configured in NI-MAX). This will introspect the capabilities of the device
and add those details to capabilities.json. To generate labscript device classes for all
devices whose capabilities are known, run `generate_classes.py`. Subclasses of NI_DAQmx
will be made in the `models` subfolder, and they can then be imported into labscript code with:

..code-block:: python

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

NI Multifunction DAQs generally provide hardware channels for the :ref:`StaticAnalogOut <labscript/StaticAnalogOut>`, :ref:`StaticDigitalOut <labscript/StaticDigitalOut>`, :ref:`AnalogOut <labscript/AnalogOut>`, :ref:`DigitalOut <labscript/DigitalOut>`, and :ref:`AnalogIn <labscript/AnalogIn>` labscript quantities for use in experiments. Exact numbers of channels, performance, and configuration depend on the model of DAQ used.

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

NI DAQs are also used within labscript to provide a :ref:`WaitMonitor <labscript/waitmonitor>`. When configured, the `WaitMonitor` allows for arbitrary-length pauses in experiment execution, waiting for some trigger to restart. The monitor provides a measurement of the duration of the wait for use in interpreting the resulting data from the experiment.

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

Note that the counter connection is specified using the logical label `'ctr0'`. On many NI DAQs, the physical connection to this counter is PFI9. The physical wiring for this configuration would have port0/line0 wired directly to PFI9, which PFI1 being sent to the master pseudoclock retriggering system in case of timeout. If timeouts are not expect/represent experiment failure, this physical connection can be omitted.


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
