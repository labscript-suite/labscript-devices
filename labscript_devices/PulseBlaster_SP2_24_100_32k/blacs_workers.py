#####################################################################
#                                                                   #
# /labscript_devices/PulseBlaster_SP2_24_100_32k/blacs_workers.py   #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from labscript_devices.PulseBlaster_No_DDS.blacs_workers import PulseblasterNoDDSWorker


    
    
class PulseBlaster_SP2_24_100_32k_Worker(PulseblasterNoDDSWorker):
    core_clock_freq = 100.0
