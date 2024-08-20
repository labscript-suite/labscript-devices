PrawnDO
=======

This labscript device controls the `PrawnDO <https://github.com/labscript-suite/prawn_digital_output>`_
open-source digital output generator based on the
`Raspberry Pi Pico <https://www.raspberrypi.org/documentation/rp2040/getting-started/>`_ platform.
It is designed to be a companion device to the :doc:`PrawnBlaster <prawnblaster>` allowing for
arbitrary digital output specification (in contrast to the variable pseudoclock generation of the PrawnBlaster).

Initial code development was in this `repository <https://github.com/pmiller2022/prawn_digital_output_labscript>`_.

Specifications
~~~~~~~~~~~~~~

The PrawnDO takes advantage of the specs of the Pico to provide the following:

* 16 synchronous digital outputs with timing specs equivalent to the PrawnBlaster
  
  - Timing resolution for an update is 1 clock cycle (10 ns at default 100 MHz clock)
  - Minimum time between updates (on any output) is 5 clock cycles (50 ns with 100 MHz clock)
  - Maximum time between updates (on any output) is 2^32-1 clock cycles (~42.9 s with 100 MHz clock)
  - Updates are internally timed (ie only initial triggering is needed, not for every update)

* 30,000 instructions (where each instruction can be held between 5 and 2^32-1 clock cycles)
* Support for external hardware triggers to begin and re-start execution after a wait.
* Can be referenced to an external LVCMOS clock
* Internal clock can be set up to 133 MHz (which scales timing specs accordingly)


Installation
~~~~~~~~~~~~

In order to turn the standard Pico into a PrawnDO, you need to load the custom firmware
available in the `Github repo <https://github.com/labscript-suite/prawn_digital_output/releases>`_ onto the board.
The simplest way to do this is by holding the reset button on the board while plugging the USB into a computer.
This will bring up a mounted folder that you copy-paste the firmware to.
Once copied, the board will reset and be ready to go.

Note that this device communicates using a virtual COM port.
The number is assigned by the controlling computer and will need to be determined in order for BLACS to connect to the PrawnDO.


Usage
~~~~~

The pinout for the PrawnDO is as follows:

* Outputs 0-15: GPIO pins 0-15, respectively.
* External Trigger input: GPIO 16
* External Clock input: GPIO 20

Note that signal cables should be connected to the Pico digital grounds for proper operation.

The PrawnDO can provide up to 16 digital outputs, which are accessed via `name.outputs`.
Each channel is specified using with a string of the form `'doD'`, where `'D'` is the GPIO number
(i.e. `'do10'`, is the specification for GPIO 10 of the PrawnDO).

An example connection table that uses the PrawnBlaster and PrawnDO:

.. code-block:: python

    from labscript import *

    from labscript_devices.PrawnBlaster.labscript_devices import PrawnBlaster
    from labscript_devices.PrawnDO.labscript_devices import PrawnDO

    PrawnBlaster(name='prawn', com_port='COM6', num_pseudoclocks=1)

    PrawnDO(name='prawn_do', com_port='COM5', clock_line=prawn.clocklines[0])

    DigitalOut('do0', prawn_do.outputs, 'do0')
    DigitalOut('do1', prawn_do.outputs, 'do1')
    DigitalOut('do12', prawn_do.outputs, 'do12')

    if __name__ == "__main__":

        start()

        stop(1)

.. note::

    The PrawnDO is designed to be directly connected to a Clockline,
    something not normally done for internally-timed devices in labscript.
    This is merely for simplicity under the most typical use case of
    adding standard digital output capability to a PrawnBlaster master pseudoclocking device.

    When used in this way, the PrawnDO can share the Clockline with other devices,
    especially with other PrawnDO boards allowing for significant fan-out.
    Nominally, the PrawnDO will ignore clock ticks from other devices on the same Clockline,
    such as a DAQ.
    However, standard cautions should be taken when sharing a clockline between devices
    (i.e. don't overload the physical output driver with too many parallel devices, 
    limit the number of devices doing fast things at nearly the same times,
    validate critical timings/operations independently). 

The PrawnDO can also be triggerd from a standard DigitalOut Trigger.
In this case, the `clock_line` argument is not used,
but the standard `trigger_device` and `trigger_connection` arguments.

Synchronization
---------------

The PrawnDO generates output based on internal timing with external starting triggers
in a manner nearly equivalent to the PrawnBlaster.
This means that under a typical use case of a PrawnBlaster used with a PrawnDO,
the output timings of the devices will drift as their internal clocks drift.
Each Pico is specified to have a clock with better than 50 ppm stability,
meaning drift could be as bad as 100 ppm between two devices 
(e.g. 100 microsecond drift after 1 second of run time).
In practice, relative drift is often around 5 ppm.

To overcome this, either use labscript waits right before time-sensitive operations
to resynchronize back to within a single clock cycle (:math:`\pm10` ns),
or use a common external clock for both devices.

Unless buffering/level protecting circuitry is used,
both the PrawnBlaster and the PrawnDO require LVCMOS square-wave clock signals.
An example evaluation board with a flexible, multi-channel LVCMOS clock generator is
the SI535X-B20QFN-EVB.
Note that interrupting the external clock can cause the Pico serial communication to freeze.
Recovery requires resetting the board via a power cycle or shorting the RUN pin to ground
to re-enable default options including the internal clock.

An example connection table using external clocks with the default frequency of 100 MHz is:

.. code-block:: python

    from labscript import *

    from labscript_devices.PrawnBlaster.labscript_devices import PrawnBlaster
    from labscript_devices.PrawnDO.labscript_devices import PrawnDO

    PrawnBlaster(name='prawn', com_port='COM6', num_pseudoclocks=1,
                 external_clock_pin=20)

    PrawnDO(name='prawn_do', com_port='COM5', clock_line=prawn.clocklines[0],
            external_clock=True)

    DigitalOut('do0', prawn_do.outputs, 'do0')
    DigitalOut('do1', prawn_do.outputs, 'do1')
    DigitalOut('do12', prawn_do.outputs, 'do12')

    if __name__ == "__main__":

        start()

        stop(1)


Input/Output Buffers
--------------------

While the PrawnBlaster and PrawnDO boards can be used as is,
it is often a good idea to add unity-gain channel buffers to the inputs and outputs.
Using buffers and line drivers from a LVCMOS family with 5V/TTL tolerant inputs can provide
compatibility with TTL inputs and drive higher capacitance loads (such a long BNC cables) more reliably.
An example that implements these buffers can be found `here <https://github.com/naqslab/PrawnDO_Breakout_Connectorized>`_.

Waits
-----

All waits in the PrawnDO are indefinite waits in the parlance of the PrawnBlaster.
This means they will never time out, but must have an external trigger to restart execution.
Changing a digital output state concurrently with a wait
results in the PrawnDO output holding the updated value during the wait.
For example, in the following code snippet, the output of `do0` will be low during the wait.
For the output of `do0` to remain high during the wait,
the second instruction (`do0.go_low(t)`) must be at least 5 clock cycles after the wait start time.

.. code-block:: python

    t = 0
    do0.go_high(t)
    t = 1e-3
    wait('my_wait', t)
    do0.go_low(t)

Detailed Documentation
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: labscript_devices.PrawnDO
    :members:
    :undoc-members:
    :show-inheritance:
    :private-members:

.. automodule:: labscript_devices.PrawnDO.labscript_devices
    :members:
    :undoc-members:
    :show-inheritance:
    :private-members:

.. automodule:: labscript_devices.PrawnDO.blacs_tabs
    :members:
    :undoc-members:
    :show-inheritance:
    :private-members:

.. automodule:: labscript_devices.PrawnDO.blacs_workers
    :members:
    :undoc-members:
    :show-inheritance:
    :private-members:

.. automodule:: labscript_devices.PrawnDO.runviewer_parsers
    :members:
    :undoc-members:
    :show-inheritance:
    :private-members: