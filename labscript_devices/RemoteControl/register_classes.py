from labscript_devices import register_classes

register_classes(
    'RemoteControl',
    BLACS_tab='user_devices.RemoteControl.blacs_tabs.RemoteControlTab',
    runviewer_parser=None
)