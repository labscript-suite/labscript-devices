Novatech DDS 9m
===============

Labscript device for control of the Novatech DDS9m synthesizer. 
With minor modifications, it can also control the Novatech 409B DDS.

.. note::
	The following text is copied from the old labscriptsuite.org blog.
	Its information dates from 2014.

The DDS9m has four outputs, the first two of which can be stepped through a pre-programmed table,
with the remaining two only controllable by software commands (and hence static during buffered runs).
We use a revision 1.3 board,
which supports external timing of the table mode, as detailed in `Appendix A of the Manual <https://www.novatechsales.com/PDF_files/dds9man.pdf>`_.

The clocking of the DDS9m through the table entries is non-trivial, however we have converged on an implementation which reliably updates the output on rising clock edges.
Here we will detail the hardware involved, along with the software commands sent from the BLACS tab, and the resulting behaviour of the device.

Hardware
~~~~~~~~

We have installed each DDS9m board in a box with a power supply, rf switches and rf amplifiers, creating what we refer to as a Supernova.
Each channel of the DDS9m is fed into a switch, with one output port going to the amplifier,
and the other going directly to the front panel for debugging (though this isn’t necessary, we don’t use this feature often).
The direction of the output (amp. vs test) is determined by a toggle switch for each channel.
The on/off state of each switch is then determined by a second toggle switch for each channel, which can switch between on, off and TTL modes.
In TTL mode the state of the switch is determined by the high/low state of a TTL line connected to a BNC port on the front panel.
We use these TTL lines to switch our rf during the experiment, since it saves on lines in the DDS9m’s table, and allows some control of the static channels.

To step through the table, we use a TTL clocking line, along with a “table enable” TTL line, to drive a tri-state driver chip,
which in turn drives pins 10 and 14 of the DDS9m.
The roles of the pins (for the rev. 1.3 boards and later) when in table mode, with hardware output enabled, are as follows:
falling edges on pin 10 cause the next table entry to be loaded into the buffer, and rising edges on pin 14 cause the values in the buffer to be output.
Since pin 14 is usually an output when I e hardware output has not been enabled,
it should not be directly connected to pin 10, as this interferes with operation during manual mode (and possibly programming of the table?).
For this same reason, you should not hold pin 14 high or low when not in hardware table mode, hence the use of a tri-state buffer.

We use an M74HC125B1R quad tri-state driver in the following configuration:

.. image:: /img/NT_DDS9m_schemeit-project.png

The clock line used to step through the table is sent to two channels of the buffer, which are connected to pins 10 and 14 of the DDS9m.
Our table enable line passes through another channel of the buffer and has its output inverted by a transistor before feeding the disable lines of the other channels of the buffer.
The result is that when the enable line is low, the buffer is disabled,
meaning that the DDS9m pins see a high impedance, and importantly, are isolated from each other since they are on their own channels.
When the enable pin is high, the buffer is enabled, and the signal from the clock line is sent to both pins.

Since the one clock line feeds both pins, when it goes high the output is updated, and when it goes low the next value is loaded into the buffer in preparation for the next clock tick.

.. note::
	Alternate circuits that do not involve tri-state buffering are described in the `mailing list <https://groups.google.com/g/labscriptsuite/c/Bf4UJMgmky0/m/xI0-q5x7AAAJ>`_.

Software implementation
~~~~~~~~~~~~~~~~~~~~~~~

Manual/static mode
------------------

When the Novatech BLACS tab is in static mode, the device operates in “automatic update” mode, having had the I a command called.
When front panel values are changed, the appropriate Fn, Vn, or Pn command is sent, and the output updates without the need for any extra hardware trigger.

Table/buffered mode
-------------------

When the Novatech BLACS tab transitions to buffered mode, it executes commands in a very specific order.
Firstly, the “static” channels (2 & 3) are programmed using the same method as manual mode, then the values for the buffered channels (0 & 1) are programmed in.
Since it takes a considerable amount of time to program a full table over the slow RS232 connection, we have implemented “smart programming”,
where the table to be programmed is compared with the last table programmed into the device.
Only the lines which have changed are reprogrammed, overwriting those values in the DDS9m’s table, but keeping all other previous values as they are.
If you suspect that your table has become corrupt you can always force a “fresh program” where BLACS‘ “smart cache” is cleared and the whole table is programmed.

Once the table has been written, we sent the mt command to the board, which places it in table mode.
Since we are still in I a auto update mode at this point, the first entry of the table is not only loaded into the buffer, but output too.
At this point, all channels on the board are outputting the instruction set at their initial output time for the experiment to be run.
We now send the I e command to switch to hardware updating, and wait for the experiment to begin.

As the experiment starts, the table enable line must be set to go high at the board’s initial output time, and the clocking line will go high too.
This initial rising edge will do nothing, since the device is already outputting the values in its buffer.
The first falling edge will then load the second line of the table into the buffer, ready for the second rising edge to trigger the output of the second value, and so on.

On transition to manual, at the end of the experiment, m 0 is sent to put the board back into manual mode, and I a is sent to turn automatic updating of the outputs again.
The last values of the experiment are then programmed in via the normal manual update mode to keep the front panel consistent with the output.

Detailed Documentation
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: labscript_devices.NovaTechDDS9M
	:members:
	:undoc-members:
	:show-inheritance:
	:member-order: bysource
	:private-members: