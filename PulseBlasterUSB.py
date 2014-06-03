from labscript_devices.PulseBlaster_No_DDS import PulseBlaster_No_DDS

class PulseBlasterUSB(PulseBlaster_No_DDS):
    description = 'SpinCore PulseBlasterUSB'        
    clock_limit = 8.3e6 # can probably go faster
    clock_resolution = 20e-9
    n_flags = 24
