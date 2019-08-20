# Wrapped structures found in the header file and the SDK docs.

import sys
import ctypes

class ColorDemosaicInfo(ctypes.Structure):
    """ iX and iY are the image dimensions. The number
        of elements in the input red, green and blue 
        arrays is iX * iY. 
        iAlgorithm sets the algorithm to use: 0 for a 
        2 x 2 matrix demosaic algorithm or 1 for a 
        3 x 3 one.
        iXPhase and iYPhase store what color is in the
        bottom left pixel.
        iBackground sets the numerical value to be 
        removed from every pixel in the input image 
        before demosaicing is done. """
    _fields_ = [
    ('iX', ctypes.c_int), # Number of X pixels, >2 
    ('iY', ctypes.c_int), # Number of Y pixels, >2
    ('iAlgorithm', ctypes.c_int), # Algorithm to demosaic
    ('iXPhase', ctypes.c_int), # First pixels in data, (cyan, 
    ('iYPhase', ctypes.c_int), # or yellow, magenta or green).
    ('iBackground', ctypes.c_int), # Background to remove
    ]


class AndorCapabilities(ctypes.Structure):
    """ Store capabilities fields, ulSize has to be initialized
        using "sizeof" """
    _fields_ = [
    ('ulSize', ctypes.c_ulong),
    ('ulAcqModes', ctypes.c_ulong),
    ('ulReadModes', ctypes.c_ulong),
    ('ulTriggerModes', ctypes.c_ulong),
    ('ulCameraType', ctypes.c_ulong),
    ('ulPixelMode', ctypes.c_ulong),
    ('ulSetFunctions', ctypes.c_ulong),
    ('ulGetFunctions', ctypes.c_ulong),
    ('ulFeatures', ctypes.c_ulong),
    ('ulPCICard', ctypes.c_ulong),
    ('ulEMGainCapability', ctypes.c_ulong),
    ('ulFTReadModes', ctypes.c_ulong),
    ]

    def __init__(self):
        self.ulSize = sys.getsizeof(self)