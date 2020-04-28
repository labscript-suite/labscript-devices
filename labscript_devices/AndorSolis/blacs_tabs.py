#####################################################################
#                                                                   #
# /labscript_devices/AndorSolis/blacs_tabs.py                       #
#                                                                   #
# Copyright 2019, Monash University and contributors                #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

from labscript_devices.IMAQdxCamera.blacs_tabs import IMAQdxCameraTab

class AndorSolisTab(IMAQdxCameraTab):

    worker_class = 'labscript_devices.AndorSolis.blacs_workers.AndorSolisWorker'