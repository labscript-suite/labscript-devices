User Devices
============

Adding custom devices for use in the labscript-suite can be done using the `user_devices` mechanism. This mechanism provides a simple way to add support for a new device without directly interacting with the **labscript-devices** repository. This is particularly useful when using standard installations of labscript, using code that is proprietary in nature, or code that, while functional, is not mature enough for widespread dissemination.

This is done by adding the **labscript-device** code into the `userlib/user_devices` folder. Using the custom device in a **labscript** connection table is then done by:

.. code-block:: python

	from user_devices.MyCustomUserDevice.labscript_devices import MyCustomUserDevice

This import statement assumes your custom device follows the new device structure organization. 

Note that both the `userlib` path and the `user_devices` folder name can be custom configured in the `labconfig.ini` file. The `user_devices` folder must be in the `userlib` path. If a different `user_devices` folder name is used, the import uses that folder name in place of `user_devices` in the above import statement.

Note that we highly encourage everyone that adds support for new hardware to consider making a pull request to **labscript-devices** so that it may be added to the mainline and more easily used by other groups.