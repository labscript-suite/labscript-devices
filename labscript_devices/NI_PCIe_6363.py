#####################################################################
#                                                                   #
# /NI_PCIe_6363.py                                                   #
#                                                                   #
# Copyright 2012, Monash University                                 #
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
        'labscript_devices.NI_DAQmx.labscript_devices': [
            'NI_PCIe_6363',
        ],
    },
)
