#####################################################################
#                                                                   #
# /labscript_devices/PulseBlaster_SP2_24_100_32k/labscript_devices.py #
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


class PulseBlaster_SP2_24_100_32k(PulseBlaster_No_DDS):
    description = 'SpinCore PulseBlaster-SP2-24-100-32k'
    clock_limit = 5.0e6
    clock_resolution = 10e-9
    n_flags = 24
    core_clock_freq = 100.0
    
    def __init__(self, *args, **kwargs):
        if 'max_instructions' not in kwargs:
            kwargs['max_instructions'] = 32000
        PulseBlaster_No_DDS.__init__(self, *args, **kwargs)
