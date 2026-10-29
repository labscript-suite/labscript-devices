Narwhal Devices Pulse Generator
===============================

This labscript device controls the `Narwhal Devices Pulse Generator <https://github.com/Narwhal-Devices/narwhaldevs-pulsegen>`_,
a 24-channel digital pattern generator with a 10 ns clock cycle.
Each channel can be a pseudoclock clockline for other devices or a digital output.

Specifications
~~~~~~~~~~~~~~

* 24 digital channels, each a clockline or a direct digital output
* 10 ns clock cycle; a clock tick on a clockline lasts at least 20 ns
* 8192 instructions, each lasting up to 2\ :sup:`48` cycles (32 days) and repeated up to 2\ :sup:`32` times
* Hardware trigger input, which starts the shot when the device is a secondary pseudoclock and ends waits
* Waits measured by the device itself, with 10 ns resolution, and resumed by software when they time out
* Trigger output pulse at the start of each run, with configurable length and delay
* Powerline synchronisation: the start of the shot and the end of each wait can be aligned with the next
  positive zero crossing of the mains, plus a delay
* Internal or external reference clock
* USB serial connection at 12 Mbaud; the device is found by its serial number

Installation
~~~~~~~~~~~~

The device needs firmware 1.002 or later; BLACS reports an error if the firmware is older. The serial
protocol is implemented in this package, so no other Python package is needed, including the vendor's
``ndpulsegen`` package.

The pulse generator connects by USB through an FTDI bridge, which the operating system presents as a
serial port. The port is opened with :func:`labscript_devices.common.usbserial.Serial`, which sets the latency
timer of the bridge to 1 ms on Linux and Windows. On Windows this requires FTDI's D2XX library, which
Windows normally installs with FTDI's driver when the device is first plugged in. Without it, each reply
from the device can be delayed by up to 16 ms. The library is available from
`FTDI <https://ftdichip.com/drivers/d2xx-drivers/>`_.

BLACS finds the device by its serial number. It only looks at the serial ports of Alchitry Au
boards, which the pulse generator is built on. With ``serial_number=None`` it uses the one pulse
generator that it finds. If another program has one of these ports open, BLACS can't tell whether
that port is a second pulse generator, so it reports an error and asks for a serial number.

On Windows this check is less precise. Windows doesn't say which product a port belongs to while
another program has it open, or at all if D2XX isn't installed. So a busy port on any device with the
same FTDI chip, such as another FPGA board, also causes the error. Giving the serial number in the
connection table avoids it.

The BLACS tab shows the serial number, hardware and firmware version and port of the device that it
is connected to. To list the pulse generators that are connected:

.. code-block:: python

   from labscript_devices.NarwhalPulseGenerator.driver import find_ports, open_port

   for port in find_ports():
       device = open_port(port)
       print(port, device.info.serial_number)
       device.close()

A port that another program has open cannot be opened, so BLACS must be the only program connected to the
device. If another program holds the port, BLACS retries for five seconds and then reports an error that
names the port.

Linux
-----

.. code-block:: bash

   sudo tee /etc/udev/rules.d/99-narwhal-pulse-generator.rules > /dev/null << 'EOF'
   # Read and write access for every user to the serial ports of Alchitry Au boards
   SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6010", ATTRS{product}=="Alchitry Au", MODE="0666"
   # Interface 0 of an Alchitry Au board is its JTAG interface: unbind the serial driver from it
   ACTION=="bind", SUBSYSTEM=="usb", DRIVER=="ftdi_sio", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6010", ATTR{interface}=="Alchitry Au", ATTR{bInterfaceNumber}=="00", RUN+="/bin/sh -c 'echo %k > /sys/bus/usb/drivers/ftdi_sio/unbind'"
   EOF
   sudo udevadm control --reload-rules

Then unplug the device and plug it in again. The first rule gives every user access to the device's serial
port, which otherwise belongs to the group ``dialout`` (Debian, Ubuntu, Fedora) or ``uucp`` (Arch), and can
only be opened by members of that group. The second rule removes the serial port of the first channel of
the FTDI bridge, which is the device's JTAG interface. The driver does not open that port, but other
programs that probe every serial port can hang for 30 s when they close it
(`narwhaldevs-pulsegen issue 1 <https://github.com/Narwhal-Devices/narwhaldevs-pulsegen/issues/1>`_).

Usage
~~~~~

The device creates one pseudoclock, ``name.pseudoclock``, and one intermediate device for its digital
outputs, ``name.direct_outputs``. Clocklines are connected to the pseudoclock and digital outputs and
triggers to the direct outputs, each with a connection ``'channel n'`` where ``n`` is 0 to 23.
A channel that the shot does not use keeps the value set on the BLACS front panel.

.. code-block:: python

   from labscript import *
   from labscript_devices.NarwhalPulseGenerator.labscript_devices import NarwhalPulseGenerator
   from labscript_devices.NI_DAQmx.models.NI_USB_6363 import NI_USB_6363

   NarwhalPulseGenerator(name='pulsegen', serial_number=12582921)

   ClockLine(name='daq_clock', pseudoclock=pulsegen.pseudoclock, connection='channel 0')
   NI_USB_6363(name='daq', MAX_name='Dev1', parent_device=daq_clock,
               clock_terminal='/Dev1/PFI0', acquisition_rate=100e3)
   AnalogOut('ao0', daq, 'ao0')
   AnalogOut('ao1', daq, 'ao1')

   DigitalOut(name='shutter', parent_device=pulsegen.direct_outputs, connection='channel 1')
   Trigger(name='camera_trigger', parent_device=pulsegen.direct_outputs, connection='channel 2')

   if __name__ == '__main__':
       start()
       shutter.go_high(1e-3)
       ao0.ramp(t=1e-3, duration=10e-3, initial=0, final=1, samplerate=100e3)
       shutter.go_low(11e-3)
       stop(12e-3)

A second pulse generator can be a secondary pseudoclock, triggered from a direct output of the first:

.. code-block:: python

   Trigger(name='pulsegen2_trigger', parent_device=pulsegen.direct_outputs, connection='channel 3')
   NarwhalPulseGenerator(name='pulsegen2', serial_number=12582922,
                         trigger_device=pulsegen2_trigger, trigger_connection='trigger')

Waits
-----

As the master pseudoclock the device measures its own waits and resumes a wait that reaches its timeout,
so no other wait monitor is needed. A wait ends on a rising edge at the hardware trigger input. Pass
``use_wait_monitor=False`` to use another device as the wait monitor.

.. fragment

.. code-block:: python

   if __name__ == '__main__':
       start()
       shutter.go_high(1e-3)
       # Pause until a rising edge at the trigger input, or resume after 2 s:
       t = 2e-3
       t += wait('atoms_loaded', t, timeout=2)
       shutter.go_low(t)
       stop(t + 1e-3)

The measured durations are saved in the shot file in ``/data/waits``, with ``timed_out`` set for a wait
that was resumed at its timeout.

A wait at ``t=0`` makes a master pulse generator start the shot on a hardware trigger, with the outputs at
their front panel values until then. labscript does not allow a wait at ``t=0`` when there is a wait
monitor, so this needs ``use_wait_monitor=False`` and no other wait monitor, and the wait is not measured.

Powerline synchronisation
-------------------------

With ``trigger_on_powerline=True`` every trigger that the device receives, including the software trigger
that starts the shot and the triggers that end waits, takes effect at the next positive zero crossing of
the mains plus ``powerline_trigger_delay`` seconds. The device must have a powerline signal on its
powerline input; BLACS reports an error at the start of the shot if it does not.

``pulsegen.wait_for_powerline(label, t)`` is a wait that ends at the next zero crossing instead of on a
trigger, whether or not ``trigger_on_powerline`` is set. It realigns the rest of the shot with the mains
phase, and the wait monitor records its duration like any other wait.

.. fragment

.. code-block:: python

   NarwhalPulseGenerator(name='pulsegen', serial_number=12582921, powerline_trigger_delay=2e-3)

   if __name__ == '__main__':
       start()
       t = 100e-3
       # The rest of the shot starts 2 ms after the next positive zero crossing:
       t += pulsegen.wait_for_powerline('mains_sync', t)
       camera_trigger.trigger(t, duration=10e-6)
       stop(t + 1e-3)

``wait_for_powerline`` requires the device to be the master pseudoclock.

BLACS tab
---------

The tab shows the 24 channels and the state of the device, and has the manual controls of the device:
the run mode, start, software run enable, stop after the current run and reset, the hardware trigger
mode, the powerline trigger and its delay, the trigger output length and delay, and the device's
notification options with a log of the notifications it sends. The last program loaded by a shot stays
in the device, so Start replays it and the continuous run mode repeats it.

Detailed Documentation
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: labscript_devices.NarwhalPulseGenerator.labscript_devices
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.NarwhalPulseGenerator.blacs_tabs
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.NarwhalPulseGenerator.blacs_workers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.NarwhalPulseGenerator.runviewer_parsers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.NarwhalPulseGenerator.driver
   :members:
   :undoc-members:
   :show-inheritance:
