#####################################################################
#                                                                   #
# /NI_DAQmx/models/__init__.py                                      #
#                                                                   #
# Copyright 2018, Monash University, JQI, Christopher Billington    #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################

import os
import json
from labscript_devices import import_class_by_fullname

THIS_FOLDER = os.path.dirname(os.path.abspath(__file__))
CAPABILITIES_FILE = os.path.join(THIS_FOLDER, 'capabilities.json')

capabilities = {}
if os.path.exists(CAPABILITIES_FILE):
    with open(CAPABILITIES_FILE) as f:
        capabilities = json.load(f)

__all__ = []
# Import all subclasses into the global namespace:
for model_name in capabilities:
    class_name = 'NI_' + model_name.replace('-', '_')
    path = 'labscript_devices.NI_DAQmx.models.' + class_name + '.' + class_name
    globals()[class_name] = import_class_by_fullname(path)
    __all__.append(class_name)