from labscript import *
from labscript_devices.DummyPseudoclock.labscript_devices import DummyPseudoclock
from labscript_devices.SoftwareDevice.labscript_devices import SoftwareDevice

labscript_init('test.h5', new=True, overwrite=True)

DummyPseudoclock('pseudoclock')
SoftwareDevice('software_device')


def foo(shot_context, t, arg):
    print(f"hello, {arg}!")
    import lyse
    run = lyse.Run(shot_context.h5_file)
    run.save_result('x', 7)


software_device.add_function('start', foo, 'world')

start()
stop(1)
