User Devices
============

Adding custom devices for use in the **labscript-suite** can be done using the `user_devices` mechanism. 
This mechanism provides a simple way to add support for a new device without directly interacting with the **labscript-devices** repository. 
This is particularly useful when using standard installations of labscript, using code that is proprietary in nature, or code that, while functional, is not mature enough for widespread dissemination.

This is done by adding the **labscript-device** code into the `userlib/user_devices` folder. Using the custom device in a **labscript** connection table is then done by:

.. code-block:: python

	from user_devices.MyCustomUserDevice.labscript_devices import MyCustomUserDevice

This import statement assumes your custom device follows the new device structure organization. 

Note that both the `userlib` path and the `user_devices` folder name can be custom configured in the `labconfig.ini` file. 
The `user_devices` folder must be in the `userlib` path. 
If a different `user_devices` folder name is used, the import uses that folder name in place of `user_devices` in the above import statement.

Note that we highly encourage everyone that adds support for new hardware to consider making a pull request to **labscript-devices** so that it may be added to the mainline and more easily used by other groups.

3rd Party Devices
-----------------

Below is a list of 3rd party devices developed by users of the **labscript-suite** that can be used via the `user_devices` mechanism described above. 
These repositories are not tested or maintained by the **labscript-suite** development team. 
As such, there is no guarantee they will work with current or future versions of the **labscript-suite**. 
They are also not guaranteed to be free of lab-specific implementation details that may prevent direct use in your apparatus. 
They are provided by users to benefit the community in supporting new and/or unusual devices, and can often serve as a good reference when developing your own devices. 
Please direct any questions regarding these repositories to their respective owners.

* `NAQS Lab <https://github.com/naqslab/naqslab_devices>`__
* `Vladan Vuletic Group Rb Lab, MIT <https://github.com/zakv/RbLab_user_devices>`__

If you would like to add your repository to this list, :doc:`please contact us or make a pull request<labscript-suite:contributing>`.