Installation
============

Prerequiste: labscript_devices >= 2.2.0

Clone this repository into the labscript_suite directory. Typically into
:file:`userlib` or the main directory level.

Next, modify your labconfig.ini file to recognize the module by adding the following entry to the :file:`[DEFAULT]` block::

	user_devices = naqslab_devices

If more than one module of 3rd party devices are used, put all module names
as a comma separated list.


Usage
=====

Invoke in labscript scripts just like other labscript devices::

	from naqslab_devices import ScopeChannel
	from naqslab_devices.KeysightXSeries.labscript_device import KeysightXScope

Details for how to use each device are contained in the :doc:`detailed documentation <devices>` listings.