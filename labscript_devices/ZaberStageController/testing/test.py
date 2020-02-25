from labscript import *
from labscript_devices.DummyPseudoclock.labscript_devices import DummyPseudoclock

MOCK = False
# labscript_init('test.h5', new=True, overwrite=True)

from labscript_devices.ZaberStageController.labscript_devices import (
    ZaberStage,
    ZaberStageController,
)
from labscript import start, stop

DummyPseudoclock()
ZaberStageController('controller', com_port='COM1', mock=MOCK)
ZaberStage('stage', controller, 'device 1', limits=(0, 30000))

start()

stage.constant(30000)

stop(1)
