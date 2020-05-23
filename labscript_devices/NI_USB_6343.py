#####################################################################
#                                                                   #
# /NI_USB_6343.py                                                   #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from labscript_devices import deprecated_import_alias

# For backwards compatibility with old experiment scripts:
NI_USB_6343 = deprecated_import_alias(
    "labscript_devices.NI_DAQmx.labscript_devices.NI_USB_6343"
)
