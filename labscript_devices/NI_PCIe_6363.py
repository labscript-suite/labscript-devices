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
from labscript_devices import deprecated_import_alias

# For backwards compatibility with old experiment scripts:
NI_PCIe_6363 = deprecated_import_alias(
    "labscript_devices.NI_DAQmx.labscript_devices.NI_PCIe_6363"
)
