PrawnBlaster
============

This labscript device controls the `PrawnBlaster <https://github.com/labscript-suite/PrawnBlaster>`_ open-source digital pattern generator based on the `Raspberry Pi Pico <https://www.raspberrypi.org/documentation/rp2040/getting-started/>`_ platform.

Specifications
~~~~~~~~~~~~~~

The PrawnBlaster takes advantage of the specs of the Pico to provide the following:

* Configurable as 1, 2, 3, or 4 truly independent pseudoclocks. 

  - Each clock has its own independent instruction set and synchronization between clocks is not required.
  - Assuming the default internal clock of 100 MHz, each clock has:
  
    - Minimum pulse half-period of 50 ns
    - Maximum pulse half-period of 42.9 s
    - Half-period resolution of 10 ns

* 30,000 instructions (each with up to 2^32 repetitions) distributed evenly among the configured pseudoclocks; 30,000, 15,000, 10,000, and 7,500 for 1, 2, 3, 4 pseudoclocks respectively.
* Support for external hardware triggers (external trigger common to all pseudoclocks)

  - Up to 100 retriggers (labscript-suite waits) per pseudoclock
  - Each wait can support a timeout of up to 42.9 s
  - Each wait is internally monitored for its duration (resolution of +/-10 ns)

* Can be referenced to an external LVCMOS clock
* Internal clock can be set up to 133 MHz (timing specs scale accordingly)

Installation
~~~~~~~~~~~~

In order to turn the standard Pico into a PrawnBlaster, you need to load the custom firmware available in the `Github repo <https://github.com/labscript-suite/PrawnBlaster/tree/master/build/prawnblaster>`_ onto the board.
The simplest way to do this is by holding the reset button on the board while plugging the USB into a computer.
This will bring up a mounted folder that you copy-paste the firmware to. Once copied, the board will reset and be ready to go.

Note that this device communicates using a virtual COM port.
The number is assigned by the controlling computer and will need to be determined in order for BLACS to connect to the PrawnBlaster.

Usage
~~~~~

The default pinout for the PrawnBlaster is as follows:

* Pseudoclock 0 output: GPIO 9
* Pseudoclock 1 output: GPIO 11
* Pseudoclock 2 output: GPIO 13
* Pseudoclock 3 output: GPIO 15
* External Triggeer input: GPIO 0
* External Clock input: GPIO 20

Note that signal cable grounds should be connected to the digital grounds of the Pico for proper operation.

The PrawnBlaster provides up to four independent clocklines. 
They can be accessed either by `name.clocklines[int]`
or directly by their auto-generated labscript names `name_clock_line_int`.

An example connection table that uses the PrawnBlaster:

.. code-block:: python

   from labscript import *

   from labscript_devices.PrawnBlaster.labscript_devices import PrawnBlaster
   from labscript_devices.NI_DAQmx.models.NI_USB_6363 import NI_USB_6363

   PrawnBlaster(name='prawn', com_port='COM6', num_pseudoclocks=1)

   NI_USB_6363(name='daq', MAX_name='Dev1',
               parent_device=prawn.clocklines[0], clock_terminal='/Dev1/PFI0',
               acquisition_rate=100e3)

   AnalogOut('ao0', daq, 'ao0')
   AnalogOut('ao1', daq, 'ao1')

   if __name__ == '__main__':

      start(0)

      stop(1)


Detailed Documentation
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: labscript_devices.PrawnBlaster
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.PrawnBlaster.labscript_devices
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.PrawnBlaster.blacs_tabs
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.PrawnBlaster.blacs_workers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.PrawnBlaster.runviewer_parsers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members: