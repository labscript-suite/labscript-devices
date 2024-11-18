#####################################################################
#                                                                   #
# /naqslab_devices/PulseblasterESRpro300/labscript_device.py        #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from labscript_devices.PulseBlaster_No_DDS import PulseBlaster_No_DDS

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

class PulseBlasterESRPro300(PulseBlaster_No_DDS):
    description = 'SpinCore PulseBlaster ESR-PRO-300'
    clock_limit = 30.0e6 # can probably go faster
    clock_resolution = 4e-9
    n_flags = 24
    
     
