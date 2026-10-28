#####################################################################
#                                                                   #
# /labscript_devices/PulseBlaster_SP2_24_100_32k/blacs_tabs.py      #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from labscript_devices.PulseBlaster_No_DDS.blacs_tabs import Pulseblaster_No_DDS_Tab


class PulseBlaster_SP2_24_100_32k_Tab(Pulseblaster_No_DDS_Tab):
    num_DO = 24
    def __init__(self,*args,**kwargs):
        self.device_worker_class = "labscript_devices.PulseBlaster_SP2_24_100_32k.blacs_workers.PulseBlaster_SP2_24_100_32k_Worker" 
        Pulseblaster_No_DDS_Tab.__init__(self,*args,**kwargs)
