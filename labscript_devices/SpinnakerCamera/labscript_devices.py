#####################################################################
#                                                                   #
# /labscript_devices/SpinnakerCamera/labscript_devices.py           #
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

class SpinnakerCamera(IMAQdxCamera):
    description = 'Spinnaker Camera'
