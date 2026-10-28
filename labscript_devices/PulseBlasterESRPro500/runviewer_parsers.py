#####################################################################
#                                                                   #
# /labscript_devices/PulseBlasterESRPro500/runviewer_parsers.py     #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from labscript_devices.PulseBlaster_No_DDS.runviewer_parsers import (
    PulseBlaster_No_DDS_Parser,
)


class PulseblasterESRPro500Parser(PulseBlaster_No_DDS_Parser):
    num_dds = 0
    num_flags = 24
