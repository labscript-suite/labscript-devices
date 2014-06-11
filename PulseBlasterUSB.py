#####################################################################
#                                                                   #
# /pulseblasterUSB.py                                               #
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

@labscript_device
class PulseBlasterUSB(PulseBlaster_No_DDS):
    description = 'SpinCore PulseBlasterUSB'        
    clock_limit = 8.3e6 # can probably go faster
    clock_resolution = 20e-9
    n_flags = 24
    
@BLACS_tab
class PulseblasterUSBTab(Pulseblaster_No_DDS_Tab):
    # Capabilities
    num_DO = 24
    def __init__(self,*args,**kwargs):
        self.device_worker_class = PulseblasterUSBWorker 
        pulseblaster_no_dds.__init__(self,*args,**kwargs)
    
@BLACS_worker   
class PulseblasterUSBWorker(PulseblasterNoDDSWorker):
    core_clock_freq = 100.0
