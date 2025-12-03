#####################################################################
#                                                                   #
# /labscript_devices/AlliedVisionCamera/labscript_devices.py        #
#                                                                   #
# Copyright 2019, Monash University and contributors                #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

from labscript_devices.IMAQdxCamera.labscript_devices import IMAQdxCamera

def camera_id_to_int(cam_id: str) -> int:
    """Convert a string camera ID to an integer for BLACS."""
    return int.from_bytes(cam_id.encode('utf-8'), byteorder='big')

class AlliedVisionCamera(IMAQdxCamera):
    description = 'AlliedVision Camera'
