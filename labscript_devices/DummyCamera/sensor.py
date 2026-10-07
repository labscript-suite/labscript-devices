#####################################################################
#                                                                   #
# /labscript_devices/DummyCamera/sensor.py                          #
#                                                                   #
# Copyright 2026, Ian Spielman and contributors                     #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

"""A dummy camera's sensor: how big it is, and what its counts are stored as.

Both halves of the device need these. The labscript half evaluates image
functions on the grid while the shot compiles; the BLACS worker needs the same
size for a manual-mode frame, where there is no shot and so no image function.
Neither half can import the other's module -- one reaches labscript and through
it pylab, the other reaches blacs -- so they share this one, which needs neither.

Nothing here models anything. A camera returns counts; what those counts mean is
the user's image function's business, and a blank frame is what this module
offers when no function has said otherwise.
"""

import numpy as np

from labscript_utils import dedent


# What a camera's images are, everywhere: whole counts, as a sensor reads them.
# The shot file stores them in uint16 datasets and the BLACS tab expects the
# same, so an image function's floats become this before anything else sees them.
IMAGE_DTYPE = np.uint16


def sensor_size(camera_attributes):
    """The (width, height) in pixels that a dummy camera's attributes give it.

    `Width` and `Height` come from the camera's attributes, where a real
    camera's resolution comes from. A dummy camera has no sensor to fall back
    on, so they are required rather than defaulted: an image quietly the wrong
    size is worse than one that does not compile.
    """
    missing = [key for key in ('Width', 'Height') if key not in camera_attributes]
    if missing:
        msg = """A dummy camera's images are whatever size its camera_attributes
            say they are, and this camera's do not say: %s missing. Give it
            camera_attributes={'Width': ..., 'Height': ...}, the way a real
            camera is told its resolution."""
        raise ValueError(dedent(msg) % ' and '.join(missing))
    return int(camera_attributes['Width']), int(camera_attributes['Height'])


def blank_image(width, height):
    """A valid frame with nothing in it.

    What a dummy camera produces when nothing has said what it should produce:
    an exposure given no function, and the Snap button in the BLACS tab, where
    there is no shot at all. It is deliberately the least interesting image that
    is still a real one, because anything more would be this module modelling
    data, which is the user's function's job and not the camera's.
    """
    return np.zeros((height, width), dtype=IMAGE_DTYPE)
