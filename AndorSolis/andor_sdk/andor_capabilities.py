# Andor Capabilities classes from C header file & SDK docs

import enum

class caps_mask:
    @classmethod
    def check(cls, mask):
        """ Convenience method. Return a list of every flag in a mask """
        return [flag.name for flag in cls.__members__.values() if flag & mask]

class acq_mode(caps_mask, enum.IntEnum):
    SINGLE = 1
    VIDEO = 2
    ACCUMULATE = 4
    KINETIC = 8
    FRAMETRANSFER = 16
    FASTKINETICS = 32
    OVERLAP = 64

class read_mode(caps_mask, enum.IntEnum):
    FULLIMAGE = 1
    SUBIMAGE = 2
    SINGLETRACK = 4
    FVB = 8
    MULTITRACK = 16 # ... drifting? 
    RANDOMTRACK = 32
    MULTITRACKSCAN = 64

class trigger_mode(caps_mask, enum.IntEnum):
    INTERNAL = 1
    EXTERNAL = 2
    EXTERNAL_FVB_EM = 4
    CONTINOUS = 8
    EXTERNALSTART = 16
    EXTERNALEXPOSURE = 32 # Deprecated 32 BULB for EXTERNALEXPOSURE
    INVERTED = 0x40
    EXTERNAL_CHARGESHIFTING = 0x80

class camera_type(enum.IntEnum):
    PDA = 0
    IXON = 1
    ICCD = 2 
    EMCCD = 3
    CCD = 4
    ISTAR = 5
    VIDEO = 6
    IDUS = 7
    NEWTON = 8
    SURCAM = 9 
    USBICCD = 10
    LUCA = 11
    RESERVED = 12
    IKON = 13
    INGAAS = 14
    IVAC = 15
    UNPROGRAMMED = 16
    CLARA = 17
    USBISTAR = 18
    SIMCAM = 19
    NEO = 20
    IXONULTRA = 21
    VOLMOS = 22
    IVAC_CCD = 23
    ASPEN = 24
    ASCENT = 25
    ALTA = 26
    ALTAF = 27
    IKONXL = 28
    RES1 = 29
    
    @classmethod
    def get_type(cls, camtype):
        return [flag.name for flag in cls.__members__.values() if flag == camtype]
    
class pixel_mode(caps_mask, enum.IntEnum):
    x8BIT = 1
    x14BIT = 2
    x16BIT = 4
    x32BIT = 8
    MONO = 0x000000
    RGB = 0x010000
    CMY = 0x020000

class set_functions(caps_mask, enum.IntEnum):
    VREADOUT = 0x01
    HREADOUT = 0x02
    TEMPERATURE = 0x04
    MCPGAIN = 0x08 # Deprecated 0x08 GAIN/ICCDGAIN for MCPGAIN
    EMCCDGAIN = 0x10
    BASELINECLAMP = 0x20
    VSAMPLITUDE = 0x40
    HIGHCAPACITY = 0x80
    BASELINEOFFSET = 0x0100
    PREAMPGAIN = 0x0200
    CROPMODE = 0x0400
    DMAPARAMETERS = 0x0800
    HORIZONTALBIN = 0x1000
    MULTITRACKHRANGE = 0x2000
    RANDOMTRACKNOGAPS = 0x4000
    EMADVANCED = 0x8000
    GATEMODE = 0x010000
    DDGTIMES = 0x020000
    IOC = 0x040000
    INTELLIGATE = 0x080000
    INSERTION_DELAY = 0x100000
    GATE_STEP = 0x200000  # GATEDELAYSTEP (?)
    TRIGGERTERMINATION = 0x400000
    EXTENDEDNIR = 0x800000
    SPOOLTHREADCOUNT = 0x1000000
    REGISTERPACK = 0x2000000
    PRESCANS = 0x4000000
    GATEWIDTHSTEP = 0x8000000
    EXTENDED_CROP_MODE = 0x10000000
    SUPERKINETICS = 0x20000000
    TIMESCAN = 0x40000000

class get_functions(caps_mask, enum.IntEnum):
    TEMPERATURE = 0x01
    TARGETTEMPERATURE = 0x02
    TEMPERATURERANGE = 0x04
    DETECTORSIZE = 0x08
    MCPGAIN = 0x10 # Deprecated 0x10 GAIN/ICCDGAIN for MCPGAIN
    EMCCDGAIN = 0x20
    HVFLAG = 0x40
    GATEMODE = 0x80
    DDGTIMES = 0x0100
    IOC = 0x0200
    INTELLIGATE = 0x0400
    INSERTION_DELAY = 0x0800
    GATESTEP = 0x1000 # GATEDELAYSTEP (?) 
    PHOSPHORSTATUS = 0x2000
    MCPGAINTABLE = 0x4000
    BASELINECLAMP = 0x8000
    GATEWIDTHSTEP = 0x10000

class features(caps_mask, enum.IntEnum):
    POLLING = 1
    EVENTS = 2
    SPOOLING = 4
    SHUTTER = 8
    SHUTTEREX = 16
    EXTERNAL_12C = 32
    SATURATIONEVENT = 64
    FANCONTROL = 128
    MIDFANCONTROL = 256
    TEMPERATUREDURINGACQUISITION = 512
    KEEPCLEANCONTROL = 1024
    DDGLITE = 0x0800
    FTEXTERNALEXPOSURE = 0x1000
    KINETICEXTERNALEXPOSURE = 0x2000
    DACCONTROL = 0x4000
    METADATA = 0x8000
    IOCONTROL = 0x10000
    PHOTONCOUNTING = 0x20000
    COUNTCONVERT = 0x40000
    DUALMODE = 0x80000
    OPTACQUIRE = 0x100000
    REALTIMESPURIOUSNOISEFILTER = 0x200000
    POSTPROCESSSPURIOUSNOISEFILTER = 0x400000
    DUALPREAMPGAIN = 0x800000
    DEFECT_CORRECTION = 0x1000000
    STARTOFEXPOSURE_EVENT = 0x2000000
    ENDOFEXPOSURE_EVENT = 0x4000000
    CAMERALINK = 0x8000000
    FIFOFULL_EVENT = 0x10000000
    SENSOR_PORT_CONFIGURATION = 0x20000000
    SENSOR_COMPENSATION = 0x40000000
    IRIG_SUPPORT = 0x80000000

class em_gain(caps_mask, enum.IntEnum):
    x8_BIT = 1
    x12_BIT = 2
    LINEAR12 = 4
    REAL12 = 8
