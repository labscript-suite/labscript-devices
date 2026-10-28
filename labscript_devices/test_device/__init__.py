from labscript_devices.common.deprecation import deprecated_names

__getattr__ = deprecated_names(
    __name__,
    {
        'labscript_devices': [
            'test_device',
        ],
        'blacs_tabs': [
            'Tab',
        ],
        'blacs_workers': [
            'Worker',
        ],
        'runviewer_parsers': [
            'Parser',
        ],
    },
)
