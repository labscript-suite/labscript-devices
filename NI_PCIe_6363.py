#####################################################################
#                                                                   #
# /NI_PCIe_6363.py                                                  #
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
from labscript_devices import NIBoard

import numpy as np
import labscript_utils.h5_lock, h5py

class NI_PCIe_6363(NIBoard):
    description = 'NI-PCIe-6363'
    n_analogs = 4
    n_digitals = 32
    n_analog_ins = 32
    digital_dtype = uint32
    
@RunviewerParser
class RunviewerClass(NI_generic.RunviewerClass):
    num_digitals = 32
    
