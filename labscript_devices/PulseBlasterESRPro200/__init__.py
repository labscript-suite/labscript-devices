#####################################################################
#                                                                   #
# /labscript_devices/PulseBlasterESRPro200/__init__.py              #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from labscript_devices.common.deprecation import deprecated_names

__getattr__ = deprecated_names(
    __name__,
    {
        'labscript_devices': [
            'PulseBlasterESRPro200',
        ],
        'blacs_tabs': [
            'pulseblasteresrpro200',
        ],
        'blacs_workers': [
            'PulseblasterESRPro200Worker',
        ],
        'runviewer_parsers': [
            'PulseblasterESRPro200Parser',
        ],
    },
)
