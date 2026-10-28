#####################################################################
#                                                                   #
# /labscript_devices/LightCrafterDMD/__init__.py                    #
#                                                                   #
# Copyright 2017, Monash University                                 #
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
            'arr_to_bmp',
            'WIDTH',
            'HEIGHT',
            'BLANK_BMP',
            'ImageSet',
            'LightCrafterDMD',
        ],
        'blacs_tabs': [
            'LightCrafterTab',
        ],
        'blacs_workers': [
            'LightCrafterWorker',
        ],
    },
)
