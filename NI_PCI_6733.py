#####################################################################
#                                                                   #
# /NI_PCI_6733.py                                                   #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################

from labscript_devices import RunviewerParser
from labscript_devices import NI_generic

import numpy as np
import labscript_utils.h5_lock, h5py

@RunviewerParser
class RunviewerClass(NI_generic.RunviewerClass):
    num_digitals = 0
    