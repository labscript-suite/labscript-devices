from labscript_devices import register_classes

register_classes(
    "BS_341A",
    BLACS_tab='labscript_devices.BS_341A.BLACS_tabs.BS_341ATab',
    runviewer_parser=None,
)