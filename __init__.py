#####################################################################
#                                                                   #
# /__init__.py                                                      #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################

import importlib

__version__ = '0.1.0-dev'
__runviewer_classes__ = {}

def import_device(device):
    module = importlib.import_module('.%s'%device, 'labscript_devices')

def LabscriptDevice(class_):
    raise NotImplementedError

def BLACSTab(class_):
    raise NotImplementedError

def BLACSWorker(class_):
    raise NotImplementedError
    
def RunviewerParser(the_class):
    class_name = the_class.__module__.split('.')[-1]
    __runviewer_classes__[class_name] = the_class
    return the_class
    
def get_runviewer_class(device_class_name):
    return __runviewer_classes__[device_class_name]
    
def get_labscript_device(name):
    raise NotImplementedError
    
def get_BLACS_tab(name):
    raise NotImplementedError

def get_BLACS_worker(name):
    raise NotImplementedError
        
def get_runviewer_parser(name):
    raise NotImplementedError
    