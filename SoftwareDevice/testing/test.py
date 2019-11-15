from labscript import *
from labscript_devices.DummyPseudoclock.labscript_devices import DummyPseudoclock
from labscript_devices.SoftwareDevice.labscript_devices import SoftwareDevice

labscript_init('test.h5', new=True, overwrite=True)

DummyPseudoclock('pseudoclock')
SoftwareDevice('software_device')

def foo(shot_context, t, arg):
    print(f"hello, {arg}!")
start()

software_device.add_function('start', foo, 'world')

stop(2)
