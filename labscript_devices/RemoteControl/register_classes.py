from labscript_devices import register_classes

register_classes(
    'RemoteControl',
    BLACS_tab='labscript_devices.RemoteControl.blacs_tabs.RemoteControlTab',
    runviewer_parser=None
)