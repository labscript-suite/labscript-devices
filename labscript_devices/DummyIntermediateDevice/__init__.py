#####################################################################
#                                                                   #
# /labscript_devices/DummyIntermediateDevice/__init__.py            #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

"""
Overview
~~~~~~~~

This file represents a dummy labscript device for purposes of testing BLACS
and labscript. The device is a Intermediate Device, and can be attached to
a pseudoclock in labscript in order to test the pseudoclock behaviour
without needing a real Intermediate Device. 

You can attach an arbitrary number of outputs to this device, however we
currently only support outputs of type AnalogOut and DigitalOut. I would be
easy to extend this is anyone needed further functionality.

Usage
~~~~~

.. code-block:: python

    from labscript import *
    
    from labscript_devices.DummyPseudoclock.labscript_devices import DummyPseudoclock
    from labscript_devices.DummyIntermediateDevice.labscript_devices import DummyIntermediateDevice

    DummyPseudoclock(name='dummy_clock',BLACS_connection='dummy')
    DummyIntermediateDevice(name='dummy_device',BLACS_connection='dummy2',
                            parent_device=dummy_clock.clockline)

    DigitalOut(name='do1',parent_device=dummy_device,connection='dummy_do1')
    DigitalOut(name='do2',parent_device=dummy_device,connection='dummy_do2')

    start()
    stop(1)

Detailed Documentation
~~~~~~~~~~~~~~~~~~~~~~

"""

from labscript_devices.common.deprecation import deprecated_names

__getattr__ = deprecated_names(
    __name__,
    {
        'labscript_devices': [
            'DummyIntermediateDevice',
        ],
        'blacs_tabs': [
            'DummyIntermediateDeviceTab',
        ],
        'blacs_workers': [
            'DummyIntermediateDeviceWorker',
        ],
        'runviewer_parsers': [
            'DummyIntermediateDeviceParser',
        ],
    },
)
