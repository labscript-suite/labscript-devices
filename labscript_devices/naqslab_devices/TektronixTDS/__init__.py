#####################################################################
#                                                                   #
# /naqslab_devices/TektronixTDS/__init__.py                         #
#                                                                   #
# Copyright 2018, David Meyer                                       #
#                                                                   #
# This file is part of naqslab_devices,                             #
# and is licensed under the                                         #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from labscript_devices import deprecated_import_alias


# For backwards compatibility with old experiment scripts:
TekScope = deprecated_import_alias("naqslab_devices.TektronixTDS.labscript_device.TDS_Scope")
