#####################################################################
#                                                                   #
# /NI_DAQmx/__init__.py                                             #
#                                                                   #
# Copyright 2018, Christopher Billington                            #
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
