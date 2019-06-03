import labscript_devices

labscript_devices.register_classes(
    'TekScope',
    BLACS_tab='labscript_devices.TekScope.blacs_tabs.TekScopeTab',
    runviewer_parser=None
)
