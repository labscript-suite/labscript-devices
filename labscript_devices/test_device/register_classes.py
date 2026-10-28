import labscript_devices

labscript_devices.register_classes(
    'test_device',
    BLACS_tab='labscript_devices.test_device.blacs_tabs.Tab',
    runviewer_parser='labscript_devices.test_device.runviewer_parsers.Parser',
)
