Introduction
============

The **labscript_devices** module contains the low-level hardware interfacing code that intermediates between the :doc:`labscript <labscript:index>` API (converting **labscript** instructions into hardware instructions) as well as the :doc:`BLACS <blacs:index>` GUI (which communicates directly with the hardware).

Each "device" is made up of four classes that handle the various tasks.

* `labscript_device` (derives from :obj:`Device <labscript:labscript.labscript.Device>`)

   - Defines the interface between the **labscript** API and generates hardware instructions that can be saved to the shot h5 file.

* `BLACS_tab` (derives from :obj:`DeviceTab <blacs:blacs.device_base_class.DeviceTab>`)

   - Defines the graphical tab that is present in the **BLACS** GUI. This tab provides graphical widgets for controlling hardware outputs and visualizing hardware inputs.

* `BLACS_worker` (derives from :class:`Worker <blacs:blacs.tab_base_classes.Worker>`)

   - Defines the software control interface to the hardware. The `BLACS_tab` spawns a process that uses this class to send and receive commands with the hardware.

* `runviewer_parser`

   - Defines a software interface that interprets hardware instructions in a shot h5 file and displays them in the :doc:`runviewer <runviewer:index>` GUI.

The **labscript_suite** provides an extensive :doc:`list of device classes <devices>` for commercially available hardware.
Furthermore, it is simple to add local :doc:`user devices <user_devices>` to control instruments not already within the labscript-suite.
