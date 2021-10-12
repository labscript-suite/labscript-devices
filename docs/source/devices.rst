Devices
=========

Here is a list of all the currently supported devices.


Pseudoclocks
~~~~~~~~~~~~

Pseudoclocks provide the timing backbone of the labscript_suite.
These devices produce hardware-timed clocklines that trigger other device outputs and acquisitions.
Many pseudoclock devices also include other types of outputs, including digital voltage and DDS frequency synthesizers.

.. toctree::
   :maxdepth: 2

   devices/pulseblaster
   devices/pulseblaster_no_dds
   devices/opalkellyXEM3001
   devices/pineblaster
   devices/prawnblaster
   devices/rfblaster

NI DAQS
~~~~~~~~~~~~

The NI_DAQmx device provides a generic interface for National Instruments data acquisition hardware.
This includes digital and analog voltage I/O. These input/outputs can be either static or hardware-timed dynamically changing variables.

.. toctree::
   :maxdepth: 2

   devices/ni_daqs

Cameras
~~~~~~~~~~~~

The camera devices provide interfaces for using various scientific cameras to acquire hardware-timed images during an experiment.
They are organized by the programming API the underlies the communication to the device.
The "master" camera class which provides the core functionality and from which the others derive is the IMAQdx class.

.. toctree::
   :maxdepth: 2

   devices/IMAQdx
   devices/pylon
   devices/flycapture2
   devices/spinnaker
   devices/andorsolis


Frequency Sources
~~~~~~~~~~~~~~~~~

These devices cover various frequency sources that provide either hardware-timed frequency, amplitude, or phase updates or static frequency outputs.

.. toctree::
   :maxdepth: 2

   devices/novatechDDS9m
   devices/phasematrixquicksyn


Miscellaneous
~~~~~~~~~~~~~~~

These devices cover other types of devices.

.. toctree::
   :maxdepth: 2

   devices/alazartechboard
   devices/lightcrafterdmd
   devices/tekscope
   devices/zaberstagecontroller


Other
~~~~~~~~~~~~~~

These devices provide dummy instruments for prototyping and testing purposes of the rest of the labscript_suite as well as the FunctionRunner device which can run arbitrary code post-shot.

.. toctree::
   :maxdepth: 2

   devices/functionrunner
   devices/dummypseudoclock
   devices/dummyintermediate
   devices/testdevice
   