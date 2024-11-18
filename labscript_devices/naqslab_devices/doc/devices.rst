Devices
=======

Directory of all device classes in this repository. 

The labscript primitive subclasses are derivatives of the labscript-provided children classes used by devices in this repository. 

There are two parent classes that are not directly used, but rather provide templates for creating new devices. First is the :doc:`VISA` class that templates communication with devices through the VISA communication protocol. This uses the :std:doc:`PyVISA python wrapper <pyvisa:index>`. The second is the :doc:`SignalGenerator` class that uses the :doc:`VISA` class to template CW frequency generators.

There are two thin subclasses of the labscript_devices.PulseBlaster_No_DDS class: :doc:`PulseBlasterESRPro300` and :doc:`PulseBlaster_No_DDS_200`. They exist simply to enforce the correct core clock frequency and clock limits without any other change in functionality from the parent.

Other device classes control particular series of devices and implement functional control of their hardward to varying degrees. In general, the design philosophy is that if the device class does not set an option, it will not be interfered with when using the device class to control the instrument. This means that custom settings and configurations of each device can be used by setting them manually at the device front panel without the device class interfering.

.. toctree::
	:maxdepth: 3
	
	primitives

	VISA
	SignalGenerator

	PulseBlasterESRPro300
	PulseBlaster_No_DDS_200

	KeysightXSeries
	NovaTechDDS
	SR865
	TektronixTDS
	KeysightDCSupply
