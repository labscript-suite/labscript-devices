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
from labscript_devices import NIBoard

import numpy as np
import labscript_utils.h5_lock, h5py

class NI_PCI_6733(NIBoard):
    description = 'NI-PCI-6733'
    n_analogs = 8
    n_digitals = 0
    n_analog_ins = 0
    digital_dtype = uint32
    
    def generate_code(self, hdf5_file):
        NIBoard.generate_code(self, hdf5_file)
        if len(self.child_devices) % 2:
            raise LabscriptError('%s %s must have an even numer of analog outputs '%(self.description, self.name) +
                             'in order to guarantee an even total number of samples, which is a limitation of the DAQmx library. ' +
                             'Please add a dummy output device or remove an output you\'re not using, so that there are an even number of outputs. Sorry, this is annoying I know :).')
                             
@RunviewerParser
class RunviewerClass(NIBoard.RunviewerClass):
    num_digitals = 0
    
