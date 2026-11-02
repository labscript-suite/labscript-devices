import labscript_devices

labscript_devices.register_classes(
    'KeysightScope',
    BLACS_tab='labscript_devices.KeysightScope.blacs_tabs.KeysightScopeTab',
    runviewer_parser=None
)
