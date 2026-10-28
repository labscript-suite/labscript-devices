#####################################################################
#                                                                   #
# /labscript_devices/common/runviewer.py                            #
#                                                                   #
# Copyright 2026, Christopher Billington                            #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
import numpy as np


def rising_edge_times(clock):
    """Return the times of the rising edges of a clock that runviewer passes to a
    parser, as a (times, values) pair. A clock that is high at the first time has a
    rising edge at that time."""
    times, values = clock
    indices = np.flatnonzero(values[1:] - values[:-1] == 1) + 1
    if values[0] == 1:
        indices = np.insert(indices, 0, 0)
    return times[indices]
