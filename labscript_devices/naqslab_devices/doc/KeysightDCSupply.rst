KeysightDCSupply
================

Overview
--------

This device class controls Keysight/Agilent DC Power Supplies.

The underlying implementation is to use the outputs as StaticAnalogOut.
The type of analog quantity (voltage or current source) is configured at the
device level based on whether the outputs are voltage limited or current limited.

At present, this driver is fairly limited in its control. Most importantly,
the driver does not set both voltage and current limits (i.e. setting a max
current limit when in constant voltage mode). A modified StaticAnalogOut will
be necessary.
It is also only tested for the E364x series single output supplies. 
It is written such that multiple outputs could be supported easily, 
but that functionality is untested.

.. include:: _apidoc\naqslab_devices.KeysightDCSupply.inc
