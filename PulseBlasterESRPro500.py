from labscript_devices.PulseBlaster_No_DDS import PulseBlaster_No_DDS

class PulseBlasterESRPro500(PulseBlaster_No_DDS):
    description = 'SpinCore PulseBlaster ESR-PRO-500'
    clock_limit = 50.0e6 # can probably go faster
    clock_resolution = 4e-9
    n_flags = 21
    
