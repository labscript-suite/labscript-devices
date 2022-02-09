How to Add a Device
===================

Adding a **labscript-device** involves implementing interfaces for your hardware to different protions of the **labscript-suite**. Namely, you must provide

* A `labscript_device` that takes **labscript** high-level commands and turns them into instructions that are saved to the shot h5 file. 
* A `BLACS_worker` that handles communication with the hardware, in particular interpreting the instructions from the shot h5 file into the necessary hardware commands to configure the device.
* A `BLACS_tab` which provides a graphical interface to control the instrument via **BLACS**

Though not strictly required, you should also consider providing a `runviewer_parser`, which can read the h5 instructions and produce the appropriate shot timings that would occur. This interface is only used in **runviewer**.

General Strategy
~~~~~~~~~~~~~~~~

As a general rule, it is best to model new hardware implementations off of a currently implemented device that has similar functionality.
If the functionality is similar enough, it may even be possible to simply sub-class the currently implemented device, which is likely preferrable.

Barring the above simple solution, one must work from scratch.
It is best to begin by determining the **labscript** device class to inherit from: `Psuedoclock`, `Device`, `IntermediateDevice`.
The first is for implementing Psuedoclock devices, the second is for generic devices that are not hardware timed by a pseudoclock, and the last is for hardware timed devices that are connected to another device controlled via labscript.

The `labscript_device` implements general configuration parameters, many of which are passed to the `BLACS_worker`.
It also implements the `generate_code` method which converts **labscript** high-level instructions and saves them to the h5 file.

The `BLACS_tab` defines the GUI widgets that control the device.
This typically takes the form of using standard widgets provided by **labscript** for controlling **labscript** output primitives (ie `AnalogOut`, `DigitalOut`, `DDS`, etc).
This configuration is done in the `initialiseGUI` method.
This also specifies which BLACS workers to use and provides necessary instantiation arguments.

The `BLACS_worker` handles communication with the hardware itself and often represents the bulk of the work required to implement a new labscript device.
In general, it should provide five different methods:

* `init`: This method initialises communications with the device. Not to be confused with the standard python class `__init__` method.
* `program_manual`: This method allows for user control of the device via the `BLACS_tab`, setting outputs to the values set in the `BLACS_tab` widgets.
* `check_remote_values`: This method reads the current settings of the device, updating the `BLACS_tab` widgets to reflect these values.
* `transition_to_buffered`: This method transitions the device to buffered shot mode, reading the shot h5 file and taking the saved instructions from `labscript_device.generate_code` and sending the appropriate commands to the hardware.
* `transition_to_manual`: This method transitions the device from buffered to manual mode. It does any necessary configuration to take the device out of buffered mode and is used to read any measurements and save them to the shot h5 file as results.

The `runviewer_parser` takes shot h5 files, reads the saved instructions, and allows you to view them in **runviewer** in order to visualise experiment timing.

Code Organization
~~~~~~~~~~~~~~~~~

There are currently two supported file organization styles for a labscript-device. 

The old style has the `labscript_device`, `BLACS_tab`, `BLACS_worker`, and `runviewer_parser` all in the same file, which typically has the same name as the `labscript_device` class name.

The new style allows for arbitrary code organization, but typically has a folder named after the `labscript_device` with each device component in a different file (ie `labscript_devices.py`, `BLACS_workers.py`, etc).
With this style, the folder requires an `__init__.py` file (which can be empty) as well as a `register_classes.py` file.
This file imports :mod:`labscript-utils:labscript_utils.device_registry` via

.. code-block:: python

	from labscript_devices import register_classes

This function informs **labscript** where to find the necessary classes during import. An example for the `NI_DAQmx` device is

.. code-block:: python

	register_classes(
		'NI_DAQmx',
		BLACS_tab='labscript_devices.NI_DAQmx.blacs_tabs.NI_DAQmxTab',
		runviewer_parser='labscript_devices.NI_DAQmx.runviewer_parsers.NI_DAQmxParser',
	)

Contributions to **labscript-devices**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you decide to implement a labscript-device for controlling new hardware, we highly encourage you to consider making a pull-request to the **labscript-devices** repository in order to add your work to the **labscript-suite**.
Increasing the list of supported devices is an important way for the **labscript-suite** to continue to grow, allowing new users to more quickly get up and running with hardware they may already have.