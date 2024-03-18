Windfreak Synth
===============

This labscript device controls the Windfreak SynthHD and SynthHD Pro signal generators.

At present only static frequencies and DDS gating is supported.
This driver also supports external referencing.


Installation
~~~~~~~~~~~~

This driver requires the `windfreak` package available on pip.
If using a version of Windows older than 10,
you will need to install the usb driver available from windfreak.

Usage
~~~~~

Below is a basic script using the driver.

.. code-block:: python

    from labscript import *

    from labscript_devices.PrawnBlaster.labscript_devices import PrawnBlaster
    from labscript_devices.Windfreak.labscript_devices import WindfreakSynthHDPro

    PrawnBlaster(name='prawn', com_port='COM6', num_pseudoclocks=1)

    WindfreakSynthHDPro(name='WF', com_port="COM7")

    StaticDDS('WF_A', WF, 'channel 0')

    if __name__ == '__main__':

        WF.enable_output(0) # enables channel A (0)
        WF_A.setfreq(10, units = 'GHz')
        WF_A.setamp(-24) # in dBm
        WF_A.setphase(45) # in deg

        start(0)
        stop(1)

This driver supports the DDS Gate feature which can provide dynamic TTL control of the outputs.
This is done by enabling the `rf_enable` triggering mode on the synth,
as well as setting the correct `digital_gate` on the output.
Note that both outputs will be toggled on/off when using `rf_enable` modulation.

It also supports external referencing of the device.
The below script uses external clocking and gating features.

.. code-block:: python

   from labscript import *

   from labscript_devices.PrawnBlaster.labscript_devices import PrawnBlaster
   from labscript_devices.Windfreak.labscript_devices import WindfreakSynthHDPro
   from labscript_devices.NI_DAQmx.Models.NI_USB_6343 import NI_USB_6343

   PrawnBlaster(name='prawn', com_port='COM6', num_pseudoclocks=1)

   NI_USB_6343(name='ni_6343', parent_device=prawn.clocklines[0],
               clock_terminal='/ni_usb_6343/PFI0',
               MAX_name='ni_usb_6343',
               )

   WindfreakSynthHDPro(name='WF', com_port="COM7",
                       trigger_mode='rf enable',
                       reference_mode='external',
                       reference_frequency=10e6)

   StaticDDS('WF_A', WF, 'channel 0',
             digital_gate={'device':ni_6343, 'connection':'port0/line0'})

   if __name__ == '__main__':

      WF.enable_output(0) # enables channel A (0)
      WF_A.setfreq(10, units = 'GHz')
      WF_A.setamp(-24) # in dBm
      WF_A.setphase(45) # in deg

      t = 0
      start(t)

      # enable rf via digital gate for 1 ms at 10 ms
      t = 10e-3
      WF_A.enable(t)
      t += 1e-3
      WF_A.disable(t)

      stop(t+1e-3)


Detailed Documentation
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: labscript_devices.Windfreak
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.Windfreak.labscript_devices
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.Windfreak.blacs_tabs
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:

.. automodule:: labscript_devices.Windfreak.blacs_workers
   :members:
   :undoc-members:
   :show-inheritance:
   :private-members:
