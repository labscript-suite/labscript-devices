#####################################################################
#                                                                   #
# /labscript_devices/NovaTechDDS9M/__init__.py                      #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################
from labscript_devices.common.deprecation import deprecated_names

__getattr__ = deprecated_names(
    __name__,
    {
        'labscript_devices': [
            'bauds',
            'NovaTechDDS9M',
        ],
        'blacs_tabs': [
            'NovatechDDS9MTab',
        ],
        'blacs_workers': [
            'NovatechDDS9mWorker',
        ],
        'runviewer_parsers': [
            'RunviewerClass',
        ],
    },
)
