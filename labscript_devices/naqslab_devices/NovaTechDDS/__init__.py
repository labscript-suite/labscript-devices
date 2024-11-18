#####################################################################
#                                                                   #
# /naqslab_devices/NovaTechDDS/__init__.py                          #
#                                                                   #
# Copyright 2017, Christopher Billington, David Meyer               #
#                                                                   #
# This file is part of naqslab_devices,                             #
# and is licensed under the                                         #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from labscript_devices import deprecated_import_alias


# For backwards compatibility with old experiment scripts:
NovaTech409B = deprecated_import_alias(
    "naqslab_devices.NovaTechDDS.labscript_device.NovaTech409B")
    
NovaTech409B_AC = deprecated_import_alias(
    "naqslab_devices.NovaTechDDS.labscript_device.NovaTech409B_AC")
    
NovaTech440A = deprecated_import_alias(
    "naqslab_devices.NovaTechDDS.labscript_device.NovaTech440A")
