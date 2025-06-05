from labscript_devices import register_classes

register_classes(
    "BS_341A",
    BLACS_tab='labscript_devices.BS_Series.BLACS_tabs.BS_Tab',
    runviewer_parser=None,
)