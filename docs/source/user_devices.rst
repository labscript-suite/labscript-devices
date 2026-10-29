User Devices
============

Adding custom devices for use in the **labscript-suite** can be done using the `user_devices` mechanism. 
This mechanism provides a simple way to add support for a new device without directly interacting with the **labscript-devices** repository. 
This is particularly useful when using standard installations of labscript, using code that is proprietary in nature, or code that, while functional, is not mature enough for widespread dissemination.

The `user_devices` setting in the `[DEFAULT]` section of the labconfig file
(`~/labscript-suite/labconfig/<hostname>.ini`) is a comma-separated list of the names of
Python packages that contain labscript devices. Each package can be anywhere on the Python
search path. The default value is `user_devices`, and the default profile has a
`user_devices` folder in the `userlib` folder, which is on the search path.
A device in a user package is imported in a **labscript** connection table by its package name, for example:

.. code-block:: python

	from user_devices.MyCustomUserDevice.labscript_devices import MyCustomUserDevice

A user package must register the BLACS tab and runviewer parser of each of its devices in a
file named `register_classes.py`, which can be in any folder of the package
(see :doc:`adding_devices`). Devices that are single files with `@BLACS_tab` and
`@runviewer_parser` decorators are found only in **labscript-devices**.
BLACS and runviewer find the classes of a device by the name of its labscript device class,
so this name must be different from the names of the device classes in **labscript-devices**
and in the other user packages.

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

If you would like to add your repository to this list, :doc:`please contact us or make a pull request<labscript-suite:project/contributing>`.