AD9959DDSSweeper
================


Specifications
~~~~~~~~~~~~~~


Installation
~~~~~~~~~~~~

- **For Pi Pico (RP2040)**:  
  `dds-sweeper_rp2040.uf2 <https://github.com/QTC-UMD/dds-sweeper/releases/latest/download/dds-sweeper_rp2040.uf2>`_

- **For Pi Pico 2 (RP2350)**:  
  `dds-sweeper_rp2350.uf2 <https://github.com/QTC-UMD/dds-sweeper/releases/latest/download/dds-sweeper_rp2350.uf2>`_

On your Raspberry Pi Pico, hold down the "bootsel" button while plugging the Pico into USB port on a PC (that must already be turned on).
The Pico should mount as a mass storage device (if it doesn't, try again or consult the Pico documentation).
Drag and drop the `.uf2` file into the mounted mass storage device.
The mass storage device should unmount after the copy completes. Your Pico is now running the DDS Sweeper firmware!

Note that this device communicates using a virtual COM port.
The number is assigned by the controlling computer and will need to be determined in order for BLACS to connect to the PrawnDO.


Usage
~~~~~


An example connection table that uses the PrawnBlaster and sweeper:

.. code-block:: python

    from labscript import start, stop, add_time_marker, AnalogOut, DigitalOut, DDS, StaticDDS
    from labscript_devices.PrawnBlaster.labscript_devices import PrawnBlaster
    from labscript_devices.AD9959DDSSweeper.labscript_devices import AD9959DDSSweeper

    # prawnblaster for external timing
    prawn = PrawnBlaster(
                        name='prawn',
                        com_port='COM7',
                        num_pseudoclocks=1
                        )

    AD9959 = AD9959DDSSweeper(
                            name='AD9959', 
                            parent_device=prawn.clocklines[0],
                            com_port='COM11',
                            ref_clock_frequency=125e6,
                            pll_mult=4
                            )


    chann0 = DDS( 'chann0', AD9959, 'channel 0')
    chann1 = StaticDDS( 'chann1', AD9959, 'channel 1')
    #chann2 = DDS( 'chann2', AD9959, 'channel 2')
    chann3 = DDS( 'chann3', AD9959, 'channel 3')


    start()

    stop(1)

.. note::

Detailed Documentation
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: labscript_devices.AD9959DDSSweeper
    :members:
    :undoc-members:
    :show-inheritance:
    :private-members:

.. automodule:: labscript_devices.AD9959DDSSweeper.labscript_devices
    :members:
    :undoc-members:
    :show-inheritance:
    :private-members:

.. automodule:: labscript_devices.AD9959DDSSweeper.blacs_tabs
    :members:
    :undoc-members:
    :show-inheritance:
    :private-members:

.. automodule:: labscript_devices.AD9959DDSSweeper.blacs_workers
    :members:
    :undoc-members:
    :show-inheritance:
    :private-members:

.. automodule:: labscript_devices.AD9959DDSSweeper.runviewer_parsers
    :members:
    :undoc-members:
    :show-inheritance:
    :private-members: