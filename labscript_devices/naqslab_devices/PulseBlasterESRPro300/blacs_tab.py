#####################################################################
#                                                                   #
# /naqslab_devices/PulseblasterESRpro300/blacs_tab.py               #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from labscript_devices.PulseBlaster_No_DDS import Pulseblaster_No_DDS_Tab

# note that ESR-Pro boards only have 21 channels
# bits 21-23 are short pulse control bits
# STATE        |  23 22 21
# OFF          |    000
# ONE_PERIOD   |    001
# TWO_PERIOD   |    010
# THREE_PERIOD |    011
# FOUR_PERIOD  |    100
# FIVE_PERIOD  |    101
# SIX_PERIOD   |    110  not defined in manual, defined in spinapi.h
# ON           |    111
   
class PulseBlasterESRPro300Tab(Pulseblaster_No_DDS_Tab):
    # Capabilities
    num_DO = 24
    def __init__(self,*args,**kwargs):
        self.device_worker_class = "naqslab_devices.PulseBlasterESRPro300.blacs_worker.PulseBlasterESRPro300Worker"
        Pulseblaster_No_DDS_Tab.__init__(self,*args,**kwargs)    
