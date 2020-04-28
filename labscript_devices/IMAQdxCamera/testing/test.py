from labscript import *
from labscript_devices.PulseBlaster import PulseBlaster
from labscript_devices.DummyPseudoclock.labscript_devices import DummyPseudoclock
from labscript_devices.DummyIntermediateDevice import DummyIntermediateDevice
from labscript_devices.IMAQdxCamera.labscript_devices import IMAQdxCamera

MOCK = True
# labscript_init('test.h5', new=True, overwrite=True)

if MOCK:
    DummyPseudoclock('pseudoclock')
    DummyIntermediateDevice('intermediatedevice', parent_device=pseudoclock.clockline)
    Trigger('camera_trigger', parent_device=intermediatedevice, connection='do0')
else:
    PulseBlaster('pulseblaster')
    Trigger('camera_trigger', pulseblaster.direct_outputs, 'flag 0')

RemoteBLACS('test_remote', 'localhost')
IMAQdxCamera(
    'camera',
    camera_trigger,
    'trigger',
    serial_number=0xDEADBEEF,
    worker=test_remote,
    mock=True,
)
start()

camera.expose(1, 'test', trigger_duration=0.2)
camera.expose(1.5, 'test', trigger_duration=0.2)

stop(2)
