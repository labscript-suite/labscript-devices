#####################################################################
#                                                                   #
# /labscript_devices/PulseBlasterUSB/labscript_devices.py           #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from labscript_devices.PulseBlaster_No_DDS.labscript_devices import PulseBlaster_No_DDS


class PulseBlasterUSB(PulseBlaster_No_DDS):
    description = 'SpinCore PulseBlasterUSB'        
    clock_limit = 8.3e6 # can probably go faster
    clock_resolution = 20e-9
    n_flags = 24
    core_clock_freq = 100.0
