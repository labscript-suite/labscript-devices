from labscript_devices.NI_DAQmx.labscript_devices import NI_PCI_6733, NI_USB_6008
from labscript_devices.PulseBlasterUSB import PulseBlasterUSB

from labscript import (
    ClockLine,
    start,
    stop,
    labscript_init,
    AnalogOut,
    DigitalOut,
    StaticAnalogOut,
    StaticDigitalOut,
    AnalogIn,
    WaitMonitor,
    wait,
    add_time_marker
)

import sys
sys.excepthook = sys.__excepthook__


# labscript_init('test.h5', new=True, overwrite=True)


PulseBlasterUSB('pulseblaster')
ClockLine('output_clock', pulseblaster.pseudoclock, 'flag 0')
ClockLine('acq_trigger', pulseblaster.pseudoclock, 'flag 1')
NI_PCI_6733('Dev1', output_clock, clock_terminal='PFI0')
NI_USB_6008('Dev3', acq_trigger, 'PFI0', acquisition_rate=5000)

AnalogOut('ao0', Dev1, 'ao0')
AnalogOut('ao1', Dev1, 'ao1')

# DigitalOut('do0', Dev1, 'port0/line0')
# DigitalOut('do1', Dev1, 'port0/line1')

StaticAnalogOut('static_ao0', Dev3, 'ao0')
StaticAnalogOut('static_ao1', Dev3, 'ao1')

StaticDigitalOut('static_do0', Dev3, 'port0/line0')
StaticDigitalOut('static_do1', Dev3, 'port1/line1')

AnalogIn('ai0', Dev3, 'ai0')
AnalogIn('ai1', Dev3, 'ai1')

WaitMonitor(
    'wait_monitor',
    parent_device=pulseblaster.direct_outputs,
    connection='flag 2',
    acquisition_device=Dev1,
    acquisition_connection='Ctr0',
    timeout_device=Dev1,
    timeout_connection='port0/line0'
)

start()

ai1.acquire('acq2', 0.5, 1.0)

static_ao0.constant(3)
static_ao1.constant(2)
static_do0.go_high()
static_do1.go_high()

t = 0
ao0.constant(t, 3)
t += 1
ai0.acquire('acq1', t, t+1)
t += ao0.ramp(t, duration=1, initial=1, final=10, samplerate=5)
# do1.go_high(t)

add_time_marker(t, 'MOT_LOAD', color=(0,64,0))

t += 1

wait('test_wait', t)

t += 1

stop(t)

# import os
# os.system('hdfview test.h5 > /dev/null')
