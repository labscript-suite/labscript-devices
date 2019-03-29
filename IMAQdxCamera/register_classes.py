#####################################################################
#                                                                   #
# /IMAQdxCamera/register_classes.py                                 #
#                                                                   #
# Copyright 2019, Monash University and contributors                #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################
from __future__ import division, unicode_literals, print_function, absolute_import
from labscript_utils import PY2

if PY2:
    str = unicode

import os
import json
from labscript_devices import register_classes

# The base class:
register_classes(
    'IMAQdxCamera',
    BLACS_tab='labscript_devices.IMAQdxCamera.blacs_tab.IMAQdxCameraTab',
    runviewer_parser=None,
)
