#####################################################################
#                                                                   #
# /labscript_devices/PrawnBlaster/__init__.py                       #
#                                                                   #
# Copyright 2021, Philip Starkey                                    #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from labscript_devices import deprecated_import_alias


# For backwards compatibility with old experiment scripts:
PrawnBlaster = deprecated_import_alias(
    "labscript_devices.PrawnBlaster.labscript_devices.PrawnBlaster"
)
