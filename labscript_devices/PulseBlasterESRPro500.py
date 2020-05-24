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
from labscript_devices import  BLACS_tab, runviewer_parser
from labscript_devices.PulseBlaster_No_DDS import PulseBlaster_No_DDS, Pulseblaster_No_DDS_Tab, PulseblasterNoDDSWorker


class PulseBlasterESRPro500(PulseBlaster_No_DDS):
    description = 'SpinCore PulseBlaster ESR-PRO-500'
    clock_limit = 50.0e6 # can probably go faster
    clock_resolution = 4e-9
    n_flags = 21
    core_clock_freq = 500.0


@BLACS_tab    
class pulseblasteresrpro500(Pulseblaster_No_DDS_Tab):
    # Capabilities
    num_DO = 21
    def __init__(self,*args,**kwargs):
        self.device_worker_class = PulseblasterESRPro500Worker 
        Pulseblaster_No_DDS_Tab.__init__(self,*args,**kwargs)
    
    
class PulseblasterESRPro500Worker(PulseblasterNoDDSWorker):
    core_clock_freq = 500.0
    
     
