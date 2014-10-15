#####################################################################
#                                                                   #
# /PulseblasterESRpro500.py                                         #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

from labscript_devices import labscript_device, BLACS_tab, BLACS_worker, runviewer_parser
from labscript_devices.PulseBlaster_No_DDS import PulseBlaster_No_DDS, Pulseblaster_No_DDS_Tab, PulseblasterNoDDSWorker
from labscript_devices.PulseBlaster import PulseBlasterParser

@labscript_device
class PulseBlaster_SP2_24_100_32k(PulseBlaster_No_DDS):
    description = 'SpinCore PulseBlaster-SP2-24-100-32k'
    clock_limit = 5.0e6
    clock_resolution = 10e-9
    n_flags = 24


@BLACS_tab    
class PulseBlaster_SP2_24_100_32k_Tab(Pulseblaster_No_DDS_Tab):
    num_DO = 24
    def __init__(self,*args,**kwargs):
        self.device_worker_class = PulseBlaster_SP2_24_100_32k_Worker 
        Pulseblaster_No_DDS_Tab.__init__(self,*args,**kwargs)
    
    
@BLACS_worker
class PulseBlaster_SP2_24_100_32k_Worker(PulseblasterNoDDSWorker):
    core_clock_freq = 100.0
    
     
@runviewer_parser
class PulseBlaster_SP2_24_100_32k_Parser(PulseBlasterParser):
    num_dds = 0
    num_flags = 24