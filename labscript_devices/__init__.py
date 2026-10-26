
import os
import sys

import numpy as np

from .__version__ import __version__

from labscript_utils.device_registry import *


def rising_edge_times(clock):
    """Return the times of the rising edges of a clock that runviewer passes to a
    parser, as a (times, values) pair. A clock that is high at the first time has a
    rising edge at that time."""
    times, values = clock
    indices = np.flatnonzero(values[1:] - values[:-1] == 1) + 1
    if values[0] == 1:
        indices = np.insert(indices, 0, 0)
    return times[indices]


if __name__ == '__main__':
    # If this module is run as __main__, make sure importing submodules still works,
    # without double-importing this file:
    __path__ = [os.path.dirname(os.path.abspath(__file__))]
    sys.modules['labscript_devices'] = sys.modules['__main__']
