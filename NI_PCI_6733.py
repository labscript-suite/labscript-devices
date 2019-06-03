#####################################################################
#                                                                   #
# /NI_PCI_6733.py                                                   #
#                                                                   #
# Copyright 2012, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from __future__ import division, unicode_literals, print_function, absolute_import
from labscript_utils import PY2

if PY2:
    str = unicode

from labscript_devices import deprecated_import_alias

# For backwards compatibility with old experiment scripts:
NI_PCI_6733 = deprecated_import_alias(
    "labscript_devices.NI_DAQmx.labscript_devices.NI_PCI_6733"
)
