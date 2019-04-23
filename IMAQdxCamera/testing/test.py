from labscript import *
from labscript_devices.PulseBlaster import PulseBlaster
from labscript_devices.IMAQdxCamera.labscript_devices import IMAQdxCamera

labscript_init('test.h5', new=True, overwrite=True)
PulseBlaster('pulseblaster')
Trigger('camera_trigger', pulseblaster.direct_outputs, 'flag 0')
RemoteBLACS('test_remote', 'localhost')
IMAQdxCamera(
    'camera', camera_trigger, 'trigger', serial_number=0xDEADBEEF, worker=test_remote
)
IMAQdxCamera('camera2', camera_trigger, 'trigger', serial_number=0xDEADBEEF)
start()

camera.expose(1, 'test', trigger_duration=0.2)
camera2.expose(1, 'test', trigger_duration=0.2)

stop(2)
