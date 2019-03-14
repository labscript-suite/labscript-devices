#####################################################################
#                                                                   #
# /labscript_devices/DummyPseudoclock/__init__.py                   #
#                                                                   #
# Copyright 2017, Christopher Billington                            #
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
DummyPseudoclock = deprecated_import_alias(
    "labscript_devices.DummyPseudoclock.labscript_devices.DummyPseudoclock"
)
