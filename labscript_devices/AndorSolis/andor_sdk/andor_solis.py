# -*- encoding: UTF8 -*-
#
# __author__ = pacosalces
#   "I'm not a wrapper"
#
import os
import sys
import platform
import ctypes
import numpy as np

from .status_codes import _SC
from .andor_structures import ColorDemosaicInfo, AndorCapabilities

# Custom ctypes
at_32 = ctypes.c_long
at_64 = ctypes.c_uint64

# Load proprietary DLL, start with current dir
current_dir = os.path.abspath(os.path.realpath(os.path.dirname(__file__)))
try:
    if 'Windows' in platform.system(): 
        # Usually found here
        dll_dir = R'C:\Program Files\Andor SOLIS\Drivers'
        sdk_dir = R'C:\Program Files\Andor SDK'
        # Usual dir exists?
        if not os.path.exists(dll_dir) and not os.path.exists(sdk_dir):
            raise OSError('Path does not exist, please set dll path')
    else:
        raise OSError("OS not supported, sorry M8")
    
except OSError:
    # Use current one
    dll_dir = current_dir

finally:
    if '64' in platform.machine():
        libname = r'atmcd64d.dll'
    else: 
        libname = r'atmcd32d.dll'
    libpath = os.path.join(dll_dir, libname)
    andor_solis = ctypes.cdll.LoadLibrary(libpath)

class AndorException(Exception):
    """ Base class for andor exceptions"""

    pass

def check_status(call_return):
    """ Queries the function call status. Based on the 
        return message, errors are handled. More info about 
        the raw messages can be found in the SDK documentation."""

    if not call_return in _SC.keys():
        raise KeyError('Unknown error call, may be fatal (lol, just kidding)')
    if 'DRV_SUCCESS' in _SC[call_return]:
        return 'DRV_SUCCESS'
    elif 'DRV_IDLE' in _SC[call_return]:
        return 'DRV_IDLE'
    elif 'DRV_NO_NEW_DATA' in _SC[call_return]:
         return 'DRV_NO_NEW_DATA'     
    elif 'DRV_TEMP_NOT_REACHED' in _SC[call_return]:
         return 'DRV_TEMP_NOT_REACHED'
    elif 'DRV_TEMP_NOT_STABILIZED' in _SC[call_return]:
         return 'DRV_TEMP_NOT_STABILIZED'
    elif 'DRV_TEMP_STABILIZED' in _SC[call_return]:
         return 'DRV_TEMP_STABILIZED'
    elif 'DRV_TEMP_DRIFT' in _SC[call_return]:
         return 'DRV_TEMP_DRIFT'     
    else:
        raw_message = "Return code: %d ... %s" % (call_return, _SC[call_return])
        raise AndorException(raw_message)

def uint_winapi(argtypes=[]):
    """ Call decorator for *pure* input functions,
        (functions that don't return anything).
        First layer takes the input arg types. """

    def args_decorator(sdk_func):
        """ Second layer sets argtypes as well as 
            the return type, which is a uint for 
            most of the methods. """
        # Get func name
        sdk_func = getattr(andor_solis, sdk_func.__name__)

        # Set func argtypes
        sdk_func.argtypes = argtypes

        # Set return type
        sdk_func.restype = ctypes.c_uint
        def wrapped_call(*args):
            """ Third layer wraps the call and 
                checks return status. """
            result = sdk_func(*[type_(arg) for type_, arg in zip(argtypes, args)])
            check_status(result)
        return wrapped_call
    return args_decorator

# \-----------------------------------------------/
# \                                               /
# \                Wrapped methods                /
# \                                               /
# \-----------------------------------------------/

STR_BUFFER_SIZE = 256

@uint_winapi()
def AbortAcquisition():
    """ This function aborts the current acquisition
        if one is active. """
    return None


@uint_winapi()
def CancelWait():
    """ This function restarts a thread which is sleeping
        within the WaitForAcquisition function. The 
        sleeping thread will return from WaitForAcquisition
        with a value not equal to DRV_SUCCESS. """
    return None


@uint_winapi()
def CoolerOFF():
    """ Switches OFF the cooling. The rate of temperature
        change is controlled in some models until the 
        temperature reaches 0 deg. Control is returned 
        immediately to the calling application. """
    return None


@uint_winapi()
def CoolerON():
    """ Switches ON the cooling. On some systems the rate 
        of temperature change is controlled until the 
        temperature is within 3 deg. of the set value. 
        Control is returned immediately to the calling 
        application. """
    return None


def DemosaicImage():
    """ Demosaics an image taken with a CYMG CCD into 
        RGB using the parameters stored in info. """

    # TODO:
    # Probably needs to set the info _fields_,
    # e.g. "info.iAlgorithm = arg_example"

    info = ColorDemosaicInfo()
    andor_solis.DemosaicImage.restype = ctypes.c_uint
    result = andor_solis.DemosaicImage(ctypes.wintypes.WORD(grey),
                                       ctypes.wintypes.WORD(red),
                                       ctypes.wintypes.WORD(green),
                                       ctypes.wintypes.WORD(blue),
                                       ctypes.byref(info))
    return None

@uint_winapi([ctypes.c_int])
def EnableKeepCleans(mode):
    """ This function is only available on certain cameras 
        operating in FVB external trigger mode. It determines 
        if the camera keep clean cycle will run between 
        acquisitions. When keep cleans are disabled in this
        way the exposure time is effectively the exposure
        time between triggers. The Keep Clean cycle is enabled 
        by default. The feature capability AC_FEATURES_KEEPCLEANCONTROL 
        determines if this function can be called for the camera. """
    return None

@uint_winapi([ctypes.c_int])
def EnableSensorCompensation(iMode):
    """ This function enables/disables the on camera 
        sensor compensation. """
    return None


@uint_winapi()
def FreeInternalMemory():
    """ The FreeInternalMemory function will deallocate any 
        memory used internally to store the previously acquired 
        data. Note that once this function has been called, 
        data from last acquisition cannot be retrived. """
    return None


def Filter_GetAveragingFactor():
    """ Returns the current averaging factor value. """
    andor_solis.Filter_GetAveragingFactor.restype = ctypes.c_uint
    averagingFactor = ctypes.c_int()
    result = andor_solis.Filter_GetAveragingFactor(ctypes.byref(averagingFactor))
    check_status(result)
    return int(averagingFactor.value)


def Filter_GetAveragingFrameCount():
    """ Returns the current frame count value. """
    andor_solis.Filter_GetAveragingFrameCount.restype = ctypes.c_uint
    frames = ctypes.c_int()
    result = andor_solis.Filter_GetAveragingFrameCount(ctypes.byref(frames))
    check_status(result)
    return int(frames.value)


def Filter_GetDataAveragingMode():
    """ Returns the current averaging mode. """
    andor_solis.Filter_GetDataAveragingMode.restype = ctypes.c_uint
    mode = ctypes.c_int()
    result = andor_solis.Filter_GetDataAveragingMode(ctypes.byref(mode))
    check_status(result)
    return int(mode.value)


def Filter_GetMode():
    """ Returns the current Noise Filter mode. """
    andor_solis.Filter_GetMode.restype = ctypes.c_uint
    mode = ctypes.c_uint()
    result = andor_solis.Filter_GetMode(ctypes.byref(mode))
    check_status(result)
    return int(mode.value)


def Filter_GetThreshold():
    """ Returns the current Noise Filter threshold value. """
    andor_solis.Filter_GetThreshold.restype = ctypes.c_uint
    threshold = ctypes.c_uint()
    result = andor_solis.Filter_GetThreshold(ctypes.byref(threshold))
    check_status(result)
    return float(threshold.value)

def GetImagesPerDMA():
    """ This function will return the maximum number of images that 
        can be transferred during a single DMA transaction. """ 
    andor_solis.GetImagesPerDMA.restype = ctypes.c_uint
    images = ctypes.c_ulong()
    result = andor_solis.GetImagesPerDMA(ctypes.byref(images))
    check_status(result)
    return int(images.value)

@uint_winapi([ctypes.c_int])
def Filter_SetAveragingFactor(averagingFactor):
    """ Sets the averaging factor to be used with the 
        recursive filter. For information on the various 
        data averaging filters available see DATA AVERAGING 
        FILTERS in the Special Guides section of the manual. """
    return None


@uint_winapi([ctypes.c_int])
def Filter_SetAveragingFrameCount(frames):
    """ Sets the number of frames to be used when using 
        the frame averaging filter. For information on the 
        various data averaging filters available see DATA 
        AVERAGING FILTERS in the Special Guides section of 
        the manual. """
    return None


@uint_winapi([ctypes.c_int])
def Filter_SetDataAveragingMode(mode):
    """ Sets the current data averaging mode. For information 
        on the various data averaging filters available see 
        DATA AVERAGING FILTERS in the Special Guides section 
        of the manual. 
        Valid options are:  0 – No Averaging Filter
                            5 – Recursive Averaging Filter
                            6 – Frame Averaging Filter """
    return None


@uint_winapi([ctypes.c_int])
def Filter_SetMode(mode):
    """ Set the Noise Filter to use; For information on 
        the various spurious noise filters available see 
        SPURIOUS NOISE FILTERS in the Special Guides section 
        of the manual. 
        Valid options are:  0 – No Filter
                            1 – Median Filter
                            2 – Level Above Filter
                            3 – Interquartile Range Filter
                            4 – Noise Threshold Filter. """
    return None


@uint_winapi([ctypes.c_float])
def Filter_SetThreshold(threshold):
    """ Sets the threshold value for the Noise Filter. For 
        information on the various spurious noise filters 
        available see SPURIOUS NOISE FILTERS in the Special 
        Guides section of the manual. 
        Valid values are:   0 – 65535 for Level Above filter.
                            0 – 10 for all other filters. """
    return None


def GetAcquiredData(shape):
    """ This function will return the data from the last 
        acquisition. The data are returned as long integers 
        (32-bit signed integers). The “array” must be large 
        enough to hold the complete data set. """
    andor_solis.GetAcquiredData.restype = ctypes.c_uint
    size = np.prod(shape)
    arr = (ctypes.c_int32 * size)()
    result = andor_solis.GetAcquiredData(ctypes.pointer(arr), ctypes.c_ulong(size))
    check_status(result)
    return np.ctypeslib.as_array(arr).reshape(shape)

def GetAcquiredData16(shape):
    """ 16-bit version of the GetAcquiredData function. 
        The “array” must be large enough to hold the 
        complete data set. """
    andor_solis.GetAcquiredData16.restype = ctypes.c_uint
    size = np.prod(shape)
    arr = (ctypes.c_uint16 * size)()  # not 100% sure this should be unsigned.
    result = andor_solis.GetAcquiredData16(ctypes.pointer(arr), ctypes.c_ulong(size))
    check_status(result)
    return np.ctypeslib.as_array(arr).reshape(shape)

def GetAcquiredFloatData(shape):
    """ This function is reserved """
    arr = (ctypes.c_float * shape[0] * shape[1])()
    size = ctypes.c_ulong(shape[0] * shape[1])
    pass


def GetAcquisitionProgress():
    """ This function will return information on the progress 
        of the current acquisition. It can be called at any 
        time but is best used in conjunction with SetDriverEvent.
        The values returned show the number of completed scans 
        in the current acquisition. 
        If 0 is returned for both accum and series then either:
        - No acquisition is currently running
        - The acquisition has just completed
        - The very first scan of an acquisition has just started 
          and not yet completed
        GetStatus can be used to confirm if the first scan has 
        just started, returning DRV_ACQUIRING, otherwise it will 
        return DRV_IDLE. For example, if accum=2 and series=3 then 
        the acquisition has completed 3 in the series and 2 
        accumulations in the 4 scan of the series. """
    andor_solis.GetAcquisitionProgress.restype = ctypes.c_uint
    acc = ctypes.c_long()
    series = ctypes.c_long()
    result = andor_solis.GetAcquisitionProgress(ctypes.byref(acc), ctypes.byref(series))
    check_status(result)
    return int(acc.value), int(series.value)

def GetAcquisitionTimings():
    """ This function will return the current “valid” acquisition 
        timing information. This function should be used after 
        all the acquisitions settings have been set, e.g. 
        SetExposureTime, SetKineticCycleTime and SetReadMode etc. 
        The values returned are the actual times used in subsequent 
        acquisitions. This function is required as it is possible 
        to set the exposure time to 20ms, accumulate cycle time 
        to 30ms and then set the readout mode to full image. As it 
        can take 250ms to read out an image it is not possible 
        to have a cycle time of 30ms. """
    andor_solis.GetAcquisitionTimings.restype = ctypes.c_uint
    # In seconds
    exp = ctypes.c_float()
    acc = ctypes.c_float()
    kin = ctypes.c_float()
    result = andor_solis.GetAcquisitionTimings(
        ctypes.byref(exp), ctypes.byref(acc), ctypes.byref(kin)
    )
    check_status(result)
    return (float(exp.value), float(acc.value), float(kin.value))

def GetAdjustedRingExposureTimes(inumTimes):
    """ This function will return the actual exposure times 
        that the camera will use. There may be differences 
        between requested exposures and the actual exposures. """
    andor_solis.GetAdjustedRingExposureTimes.restype = ctypes.c_uint
    fptimes = ctypes.c_float()
    result = andor_solis.GetAdjustedRingExposureTimes(
        ctypes.c_int(inumTimes), ctypes.byref(fptimes)
    )
    check_status(result)
    return float(fptimes.value)

def GetAllDMAData(shape):
    """ This function is reserved. """
    arr = (ctypes.c_float * shape[0] * shape[1])()
    size = ctypes.c_ulong(shape[0] * shape[1])
    pass


def GetAmpDesc(index, char_length):
    """ This function will return a string with an amplifier 
        description. The amplifier is selected using the index. 
        The SDK has a string associated with each of its 
        amplifiers. The maximum number of characters needed to 
        store the amplifier descriptions is 21. The user has to 
        specify the number of characters they wish to have 
        returned to them from this function. """
    andor_solis.GetAmpDesc.restype = ctypes.c_uint
    name = ctypes.create_string_buffer(STR_BUFFER_SIZE)
    result = andor_solis.GetAmpDesc(
        ctypes.c_int(index), ctypes.byref(name), ctypes.c_int(char_length)
    )
    check_status(result)
    return str(name.value)

def GetAmpMaxSpeed(index):
    """ This function will return the maximum available 
        horizontal shift speed for the amplifier selected by 
        the index parameter. """
    andor_solis.GetAmpMaxSpeed.restype = ctypes.c_uint
    speed = ctypes.c_float()
    result = andor_solis.GetAmpMaxSpeed(ctypes.c_int(index), ctypes.byref(speed))
    check_status(result)
    return float(speed.value)

def GetAvailableCameras():
    """This function returns the total number of Andor cameras 
        currently installed. It is possible to call this function 
        before any of the cameras are initialized. """
    andor_solis.GetAvailableCameras.restype = ctypes.c_uint
    totalCameras = ctypes.c_long()
    result = andor_solis.GetAvailableCameras(ctypes.byref(totalCameras))
    check_status(result)
    return int(totalCameras.value)


def GetBackground(shape):
    """ This function is reserved. """
    arr = (ctypes.c_float * shape[0] * shape[1])()
    size = ctypes.c_ulong(shape[0] * shape[1])
    pass


def GetBaselineClamp():
    """ This function returns the status of the baseline clamp 
        functionality. With this feature enabled the baseline 
        level of each scan in a kinetic series will be more 
        consistent across the sequence. 
            1 – Baseline Clamp Enabled
            0 – Baseline Clamp Disabled """
    andor_solis.GetBaselineClamp.restype = ctypes.c_uint
    state = ctypes.c_int()
    result = andor_solis.GetBaselineClamp(ctypes.byref(state))
    check_status(result)
    return int(state.value)


def GetBitDepth(channel):
    """ This function will retrieve the size in bits of the 
        dynamic range for any available AD channel. """
    andor_solis.GetBitDepth.restype = ctypes.c_uint
    depth = ctypes.c_int()
    result = andor_solis.GetBitDepth(ctypes.c_int(channel), ctypes.byref(depth))
    check_status(result)
    return int(depth.value)

def GetCameraEventStatus():
    """ This function will return if the system is exposing 
        or not. This is only supported by the CCI23 card. 
        The status of the firepulse will be returned that the 
        firepulse is low
            0 Fire pulse low
            1 Fire pulse high
        """
    andor_solis.GetCameraEventStatus.restype = ctypes.c_uint
    camStatus = ctypes.c_uint32()
    result = andor_solis.GetCameraEventStatus(ctypes.byref(camStatus))
    check_status(result)
    return int(camStatus.value)


def GetCameraHandle(cameraIndex):
    """ This function returns the handle for the camera specified 
        by cameraIndex. When multiple Andor cameras are installed 
        the handle of each camera must be retrieved in order to 
        select a camera using the SetCurrentCamera function. The 
        number of cameras can be obtained using the GetAvailableCameras 
        function. Valid values 0 to NumberCameras-1 where NumberCameras 
        is the value returned by the GetAvailableCameras function."""
    andor_solis.GetCameraHandle.restype = ctypes.c_uint
    cameraHandle = ctypes.c_long()
    result = andor_solis.GetCameraHandle(
        ctypes.c_long(cameraIndex), ctypes.byref(cameraHandle)
    )
    check_status(result)
    return int(cameraHandle.value)

def GetCameraInformation(index):
    """ This function will return information on a particular camera 
        denoted by the index. 
            Bit:1 1 - USB camera present
            Bit:2 1 - All dlls loaded properly
            Bit:3 1 - Camera Initialized correctly 
        Note: Only available in iDus. The index parameter is not used 
        at present so should be set to 0. For any camera except the 
        iDus The value of information following a call to this function 
        will be zero. """
    andor_solis.GetCameraInformation.restype = ctypes.c_uint
    information = ctypes.c_long()
    result = andor_solis.GetCameraInformation(
        ctypes.c_int(index), ctypes.byref(information)
    )
    check_status(result)
    return int(information.value)

def GetCameraSerialNumber():
    """ This function will retrieve camera’s serial number. """
    andor_solis.GetCameraSerialNumber.restype = ctypes.c_uint
    number = ctypes.c_int()
    result = andor_solis.GetCameraSerialNumber(ctypes.byref(number))
    check_status(result)
    return int(number.value)


def GetCapabilities():
    """ This function will fill in an AndorCapabilities structure 
        with the capabilities associated with the connected camera. 
        Before passing the address of an AndorCapabilites structure 
        to the function the ulSize member of the structure should 
        be set to the size of the structure. In C++ this can be done 
        with the line: 
            caps->ulSize = sizeof(AndorCapabilities);
        Individual capabilities are determined by examining certain 
        bits and combinations of bits in the member variables of the 
        AndorCapabilites structure. The next few pages contain a
        summary of the capabilities currently returned... (pp. 121) """
    andor_solis.GetCapabilities.restype = ctypes.c_uint
    caps = AndorCapabilities()
    result = andor_solis.GetCapabilities(ctypes.byref(caps))
    check_status(result)
    return caps


def GetControllerCardModel():
    """ This function will retrieve the type of PCI controller card 
        included in your system. This function is not applicable for 
        USB systems. The maximum number of characters that can be
        returned from this function is 10. """
    andor_solis.GetControllerCardModel.restype = ctypes.c_uint
    controllerCardModel = ctypes.create_string_buffer(STR_BUFFER_SIZE)
    result = andor_solis.GetControllerCardModel(ctypes.byref(controllerCardModel))
    check_status(result)
    return str(controllerCardModel.value)

def GetCountConvertWavelengthRange(min_wave, max_wave):
    """ This function returns the valid wavelength range available 
        in Count Convert mode. """
    andor_solis.GetCountConvertWavelengthRange.restype = ctypes.c_uint
    min_wave = ctypes.c_float()
    max_wave = ctypes.c_float()
    result = andor_solis.GetCountConvertWavelengthRange(
        ctypes.byref(min_wave), ctypes.byref(max_wave)
    )
    check_status(result)
    return float(min_wave.value), float(max_wave.value)

def GetCurrentCamera():
    """ When multiple Andor cameras are installed this function returns 
        the handle of the currently selected one."""
    andor_solis.GetCurrentCamera.restype = ctypes.c_uint
    cameraHandle = ctypes.c_long()
    result = andor_solis.GetCurrentCamera(ctypes.byref(cameraHandle))
    check_status(result)
    return int(cameraHandle.value)


def GetCYMGShift():
    """ This function is reserved. """
    iXShift = ctypes.POINTER(ctypes.c_int(iXShift))
    iYShift = ctypes.POINTER(ctypes.c_int(iYShift))
    pass


def GetDDGExternalOutputEnabled(index):
    """ This function gets the current state of a selected external 
        output. """
    andor_solis.GetDDGExternalOutputEnabled.restype = ctypes.c_uint
    enabled = ctypes.c_ulong()
    result = andor_solis.GetDDGExternalOutputEnabled(
        ctypes.c_ulong(index), ctypes.byref(enabled)
    )
    check_status(result)
    return int(enabled.value)

def GetDDGExternalOutputPolarity(index):
    """ This function gets the current polarity of a selected external 
        output. """
    andor_solis.GetDDGExternalOutputPolarity.restype = ctypes.c_uint
    polarity = ctypes.c_ulong()
    result = andor_solis.GetDDGExternalOutputPolarity(
        ctypes.c_ulong(index), ctypes.byref(polarity)
    )
    check_status(result)
    return int(polarity.value)

def GetDDGExternalOutputStepEnabled(index):
    """ Each external output has the option to track the gate step 
        applied to the gater. This function can be used to determine 
        if this option is currently active. """
    andor_solis.GetDDGExternalOutputStepEnabled.restype = ctypes.c_uint
    enabled = ctypes.c_ulong()
    result = andor_solis.GetDDGExternalOutputStepEnabled(
        ctypes.c_ulong(index), ctypes.byref(enabled)
    )
    check_status(result)
    return int(enabled.value)

def GetDDGExternalOutputTime(index):
    """This function can be used to find the actual timings for a 
        particular external output. """
    andor_solis.GetDDGExternalOutputTime.restype = ctypes.c_uint
    # In picoseconds
    delay = ctypes.c_uint64()
    width = ctypes.c_uint64()
    result = andor_solis.GetDDGExternalOutputTime(
        ctypes.c_ulong(index), ctypes.byref(delay), ctypes.byref(width)
    )
    check_status(result)
    return int(delay.value), int(width.value)

def GetDDGStepCoefficients(mode, p1, p2):
    """ This function will return the coefficients for a particular 
        gate step mode. 
            Valid values:   0 constant.
                            1 exponential.
                            2 logarithmic.
                            3 linear. """
    andor_solis.GetDDGStepCoefficients.restype = ctypes.c_uint
    p1 = ctypes.c_double()
    p2 = ctypes.c_double()
    result = andor_solis.GetDDGStepCoefficients(
        ctypes.c_ulong(mode), ctypes.byref(p1), ctypes.byref(p2)
    )
    check_status(result)
    return int(p1.value), int(p2.value)

def GetDDGStepMode():
    """ This function will return the current gate step mode. 
            Valid values:   0 constant.
                            1 exponential.
                            2 logarithmic.
                            3 linear.
                            100 off. """
    andor_solis.GetDDGStepMode.restype = ctypes.c_uint
    mode = ctypes.c_ulong()
    result = andor_solis.GetDDGStepMode(ctypes.byref(mode))
    check_status(result)
    return int(mode.value)


def GetDDGGateTime():
    """ This function can be used to get the actual gate timings 
        for a USB iStar. """
    andor_solis.GetDDGGateTime.restype = ctypes.c_uint
    delay = ctypes.c_uint64()
    width = ctypes.c_uint64()
    result = andor_solis.GetDDGGateTime(ctypes.byref(delay), ctypes.byref(width))
    check_status(result)
    return int(delay.value), int(width.value)

def GetDDGInsertionDelay():
    """ This function gets the current state of the insertion delay."""
    andor_solis.GetDDGInsertionDelay.restype = ctypes.c_uint
    state = ctypes.c_int()
    result = andor_solis.GetDDGInsertionDelay(ctypes.byref(state))
    check_status(result)
    return int(state.value)


def GetDDGIntelligate():
    """ This function gets the current state of Intelligate. """
    andor_solis.GetDDGIntelligate.restype = ctypes.c_uint
    state = ctypes.c_int()
    result = andor_solis.GetDDGIntelligate(ctypes.byref(state))
    check_status(result)
    return int(state.value)


def GetDDGIOC():
    """This function gets the current state of the integrate on chip 
       (IOC) option. """
    andor_solis.GetDDGIOC.restype = ctypes.c_uint
    state = ctypes.c_int()
    result = andor_solis.GetDDGIOC(ctypes.byref(state))
    check_status(result)
    return int(state.value)


def GetDDGIOCFrequency():
    """ This function can be used to return the actual IOC frequency 
        that will be triggered. It should only be called once all the 
        conditions of the experiment have been defined."""
    andor_solis.GetDDGIOCFrequency.restype = ctypes.c_uint
    frequency = ctypes.c_double()
    result = andor_solis.GetDDGIOCFrequency(ctypes.byref(frequency))
    check_status(result)
    return int(frequency.value)


def GetDDGIOCNumber():
    """ This function can be used to return the actual number of pulses 
        that will be triggered. It should only be called once all the 
        conditions of the experiment have been defined."""
    andor_solis.GetDDGIOCNumber.restype = ctypes.c_uint
    numberPulses = ctypes.c_ulong()
    result = andor_solis.GetDDGIOCNumber(ctypes.byref(numberPulses))
    check_status(result)
    return int(numberPulses.value)


def GetDDGIOCNumberRequested():
    """ This function can be used to return the number of pulses that 
        were requested by the user."""
    andor_solis.GetDDGIOCNumberRequested.restype = ctypes.c_uint
    pulses = at_32()
    result = andor_solis.GetDDGIOCNumberRequested(ctypes.byref(pulses))
    check_status(result)
    return int(pulses.value)


def GetDDGIOCPeriod():
    """ This function can be used to return the actual IOC period that 
        will be triggered. It should only be called once all the 
        conditions of the experiment have been defined."""
    andor_solis.GetDDGIOCPeriod.restype = ctypes.c_uint
    period = ctypes.c_uint64()
    result = andor_solis.GetDDGIOCPeriod(ctypes.byref(period))
    check_status(result)
    return int(period.value)


# ****************************************************************************

# STOPPED AT PAGE 150, at this point add only SDK functions needed for iXon Ultra.


@uint_winapi()
def Initialize(path):
    """ This function will initialize the Andor SDK System. As part 
        of the initialization procedure on some cameras (i.e. Classic, 
        iStar and earlier iXon) the DLL will need access to a DETECTOR.INI 
        which contains information relating to the detector head, number 
        pixels, readout speeds etc. """
    return None


def GetDetector():
    """ This function returns the size of the detector in pixels. The 
        horizontal axis is taken to be the axis parallel to the readout 
        register. """
    andor_solis.GetDetector.restype = ctypes.c_uint
    xpixels, ypixels = ctypes.c_int(), ctypes.c_int()
    result = andor_solis.GetDetector(ctypes.byref(xpixels), ctypes.byref(ypixels))
    check_status(result)
    return int(xpixels.value), int(ypixels.value)

def GetHeadModel():
    """ This function will retrieve the type of CCD attached 
        to your system. """
    andor_solis.GetHeadModel.restype = ctypes.c_uint
    name = ctypes.create_string_buffer(STR_BUFFER_SIZE)
    result = andor_solis.GetHeadModel(ctypes.byref(name))
    check_status(result)
    return str(name.value)


@uint_winapi()
def ShutDown():
    """ This function will close the AndorMCD system down."""
    return None


def GetHardwareVersion():
    """ This function returns the Hardware version information 
        as a dict. """
    andor_solis.GetHardwareVersion.restype = ctypes.c_uint
    PCB = ctypes.c_uint()
    Decode = ctypes.c_uint()
    dummy1 = ctypes.c_uint()
    dummy2 = ctypes.c_uint()
    CameraFirmwareVersion = ctypes.c_uint()
    CameraFirmwareBuild = ctypes.c_uint()
    result = andor_solis.GetHardwareVersion(
        ctypes.byref(PCB),
        ctypes.byref(Decode),
        ctypes.byref(dummy1),
        ctypes.byref(dummy2),
        ctypes.byref(CameraFirmwareVersion),
        ctypes.byref(CameraFirmwareBuild),
    )
    check_status(result)
    hardware_v = {
        'PCB': int(PCB.value),
        'Decode': int(Decode.value),
        'dummy1': int(dummy1.value),
        'dummy2': int(dummy2.value),
        'CameraFirmwareVersion': int(CameraFirmwareVersion.value),
        'CameraFirmwareBuild': int(CameraFirmwareBuild.value),
    }
    return hardware_v

def GetSoftwareVersion():
    """ This function returns the Software version information
        for the microprocessor code and the driver as a dict. """
    andor_solis.GetSoftwareVersion.restype = ctypes.c_uint
    eprom = ctypes.c_uint()
    cofFile = ctypes.c_uint()
    vxdRev = ctypes.c_uint()
    vxdVer = ctypes.c_uint()
    dllRev = ctypes.c_uint()
    dllVer = ctypes.c_uint()
    result = andor_solis.GetSoftwareVersion(
        ctypes.byref(eprom),
        ctypes.byref(cofFile),
        ctypes.byref(vxdRev),
        ctypes.byref(vxdVer),
        ctypes.byref(dllRev),
        ctypes.byref(dllVer),
    )
    check_status(result)
    software_v = {
        'EPROM': int(eprom.value),
        'cofFile': int(cofFile.value),
        'Driver_rev': int(vxdRev.value),
        'Driver_ver': int(vxdVer.value),
        'dll_rev': int(dllRev.value),
        'dll_ver': int(dllVer.value),
    }
    return software_v

@uint_winapi([ctypes.c_int])
def SetAcquisitionMode(mode):
    """ This function will set the acquisition mode to be used on 
        the next StartAcquisition. 
            Valid values:   
                1 Single Scan 
                2 Accumulate 
                3 Kinetics 
                4 Fast Kinetics 
                5 Run till abort 
    """
    return None


@uint_winapi([ctypes.c_int])
def SetReadMode(mode):
    """ This function will set the readout mode to be used on 
        the subsequent acquisitions.
            Valid values:   0 Full Vertical Binning 
                            1 Multi-Track
                            2 Random-Track 
                            3 Single-Track 
                            4 Image. """
    return None

@uint_winapi([ctypes.c_int, ctypes.c_int])
def SetSingleTrack(center_row, height):
    """ This function will set the single track parameters. The parameters are 
    validated in the following order: centre row and then track height.
        
        Parameters:
            int center_row: centre row of track
            
            int height: height of track

        Valid values:
            center_row:    
                Valid range 1 to number of vertical pixels.
                1 conventional/Extended NIR Mode(clara)
            heigth: 
                Valid range > 1 (maximum value depends on centre row and number of vertical pixels).
    """
    return None


@uint_winapi([ctypes.c_int, ctypes.c_int, ctypes.c_int])
def SetCropMode(active, height, reserved):
    """This function effectively reduces the dimensions of the CCD by excluding some rows or columns 
    to achieve higher throughput. In isolated crop mode iXon, Newton and iKon cameras can operate in 
    either Full Vertical Binning or Imaging read modes. iDus can operate in Full Vertical Binning read 
    mode only.
    Note: It is important to ensure that no light falls on the excluded region otherwise the acquired 
    data will be corrupted.
     Parameters:
    int active: 1 – Crop mode is ON.
                0 – Crop mode is OFF.

    int height: The selected crop height. This value must be between 1 and the CCD height.

    int reserved

    """
    return None

@uint_winapi([ctypes.c_int, ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int])
def SetIsolatedCropMode(active, height, width, vbin, hbin):
    """This function effectively reduces the dimensions of the CCD by excluding some rows or columns 
    to achieve higher throughput. In isolated crop mode iXon, Newton and iKon cameras can operate in 
    either Full Vertical Binning or Imaging read modes. iDus can operate in Full Vertical Binning read 
    mode only.
    Note: It is important to ensure that no light falls on the excluded region otherwise the acquired 
    data will be corrupted.
     Parameters:
    int active: 1 – Crop mode is ON.
                0 – Crop mode is OFF.

    int height: The selected crop height. This value must be between 1 and the CCD height.

    int cropwidth: The selected crop width. This value must be between 1 and the CCD width.

    int vbin: The selected vertical binning.

    int hbin: The selected horizontal binning.

    """
    return None

@uint_winapi([ctypes.c_int, ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int])
def SetIsolatedCropModeEx(active, height, width, vbin, hbin, cropleft, cropbottom):
    """This function effectively reduces the dimensions of the CCD by excluding some rows or columns 
    to achieve higher throughput. In isolated crop mode iXon, Newton and iKon cameras can operate in 
    either Full Vertical Binning or Imaging read modes. iDus can operate in Full Vertical Binning read 
    mode only.
    Note: It is important to ensure that no light falls on the excluded region otherwise the acquired 
    data will be corrupted.
     Parameters:
    int active: 1 – Crop mode is ON.
                0 – Crop mode is OFF.

    int height: The selected crop height. This value must be between 1 and the CCD height.

    int cropwidth: The selected crop width. This value must be between 1 and the CCD width.

    int vbin: The selected vertical binning.

    int hbin: The selected horizontal binning.

    int cropleft: crop left starting point

    int cropbottom: crop bottom starting point

    """
    return None


def GetFastestRecommendedVSSpeed():
    """ As your Andor SDK system may be capable of operating at 
        more than one vertical shift speed this function will 
        return the fastest recommended speed available. The very 
        high readout speeds, may require an increase in the 
        amplitude of the Vertical Clock Voltage using SetVSAmplitude. 
        This function returns the fastest speed which does not 
        require the Vertical Clock Voltage to be adjusted. The values 
        returned are the vertical shift speed index and the actual 
        speed in microseconds per pixel shift. """
    andor_solis.GetFastestRecommendedVSSpeed.restype = ctypes.c_uint
    index = ctypes.c_int()
    speed = ctypes.c_float()
    result = andor_solis.GetFastestRecommendedVSSpeed(
        ctypes.byref(index), ctypes.byref(speed)
    )
    check_status(result)
    return int(index.value), float(speed.value)

@uint_winapi([ctypes.c_int])
def SetVSSpeed(index):
    """ This function will set the vertical speed to be used for 
        subsequent acquisitions. 
        Valid values: 0 to GetNumberVSSpeeds - 1"""
    return None

@uint_winapi([ctypes.c_int])
def SetVSAmplitude(state):
    """ If you choose a high readout speed (a low readout time), then 
    you should also consider increasing the amplitude of the Vertical 
    Clock Voltage. There are five levels of amplitude available for you to choose from:
        0 - Normal
        +1
        +2
        +3
        +4
    Exercise caution when increasing the amplitude of the vertical clock voltage, since 
    higher clocking voltages may result in increased clock-induced charge (noise) in your signal. 
    In general, only the very highest vertical clocking speeds are likely to benefit from an 
    increased vertical clock voltage amplitude."""
    return None

def GetNumberVSSpeeds():
    """ As your Andor system may be capable of operating at more than
    one vertical shift speed this function will return the actual number 
    of speeds available."""
    andor_solis.GetNumberVSSpeeds.restype = ctypes.c_uint
    speeds = ctypes.c_int()
    result = andor_solis.GetNumberVSSpeeds(ctypes.byref(speeds))
    check_status(result)
    return int(speeds.value)


def GetVSSpeed(index):
    """ As your Andor SDK system may be capable of operating at more than
    one vertical shift speed this function will return the actual speeds 
    available. The value returned is in microseconds. """
    andor_solis.GetVSSpeed.restype = ctypes.c_uint
    speed = ctypes.c_float()
    result = andor_solis.GetVSSpeed(ctypes.c_int(index), ctypes.byref(speed))
    check_status(result)
    return float(speed.value)

def GetNumberADChannels():
    """ As your Andor SDK system may be capable of operating with 
        more than one A-D converter, this function will tell you 
        the number available. """
    andor_solis.GetNumberADChannels.restype = ctypes.c_uint
    channels = ctypes.c_int()
    result = andor_solis.GetNumberADChannels(ctypes.byref(channels))
    check_status(result)
    return int(channels.value)

def GetNumberHSSpeeds(channel, typ):
    """ As your Andor SDK system is capable of operating at more 
        than one horizontal shift speed this function will return 
        the actual number of speeds available.
        typ:    Valid values:   0 electron multiplication. 
                                1 conventional."""
    andor_solis.GetNumberHSSpeeds.restype = ctypes.c_uint
    speeds = ctypes.c_int()
    result = andor_solis.GetNumberHSSpeeds(
        ctypes.c_int(channel), ctypes.c_int(typ), ctypes.byref(speeds)
    )
    check_status(result)
    return int(speeds.value)

def GetHSSpeed(channel, typ, index):
    """ As your Andor system is capable of operating at more than 
        one horizontal shift speed this function will return the 
        actual speeds available. The value returned is in MHz. 
        typ:    Valid values:   0 electron multiplication/Conventional(clara). 
                                1 conventional/Extended NIR Mode(clara).
        index:  Valid values:   0 to NumberSpeeds-1 
        where NumberSpeeds is value returned in first parameter after a 
        call to GetNumberHSSpeeds()."""
    andor_solis.GetHSSpeed.restype = ctypes.c_uint
    speed = ctypes.c_float()
    result = andor_solis.GetHSSpeed(
        ctypes.c_int(channel),
        ctypes.c_int(typ),
        ctypes.c_int(index),
        ctypes.byref(speed),
    )
    check_status(result)
    return float(speed.value)

@uint_winapi([ctypes.c_int])
def SetADChannel(channel):
    """ This function will set the AD channel to one of the possible A-Ds 
        of the system. This AD channel will be used for all subsequent 
        operations performed by the system. 
        Valid values: 0 to GetNumberADChannels-1. """
    return None

@uint_winapi([ctypes.c_int, ctypes.c_int])
def SetHSSpeed(typ, index):
    """ This function will set the speed at which the pixels are shifted 
        into the output node during the readout phase of an acquisition. 
        Typically your camera will be capable of operating at several 
        horizontal shift speeds. To get the actual speed that an index 
        corresponds to use the GetHSSpeed function.
        
        Parameters:
            int typ: type
            
            int index: AD index

        Valid values:
            typ:    
                0 electron multiplication/Conventional(clara)
                1 conventional/Extended NIR Mode(clara)
            index: 
                0 to GetNumberHSSpeeds()-1 
    """
    return None

@uint_winapi([ctypes.c_int, ])
def SetOutputAmplifier(typ):
    """ Sets the second output amplifier
        
        Parameters:
            int typ: type
            
        Valid values:
            typ:    
                0 electron multiplication/Conventional(clara)
                1 conventional/Extended NIR Mode(clara)
    """
    return None


@uint_winapi([ctypes.c_int])
def SetBaselineClamp(state):
    """ This function turns on and off the baseline clamp functionality. 
        With this feature enabled the baseline level of each scan in a 
        kinetic series will be more consistent across the sequence.
        state:  Enables/Disables Baseline clamp functionality
            1 – Enable Baseline Clamp
            0 – Disable Baseline Clamp """
    return None

@uint_winapi([ctypes.c_float])
def SetExposureTime(time):
    """ This function will set the exposure time to the nearest valid 
        value not less than the given value. The actual exposure time 
        used is obtained by GetAcquisitionTimings. Please refer to 
        SECTION 5 – ACQUISITION MODES for further information. 
        Time should be in seconds """
    return None


@uint_winapi([ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int])
def SetShutter(typ, mode, closingtime, openingtime):
    """ This function controls the behaviour of the shutter. The typ 
        parameter allows the user to control the TTL signal output to 
        an external shutter. The mode parameter configures whether the 
        shutter opens & closes automatically (controlled by the camera) 
        or is permanently open or permanently closed. The opening and 
        closing time specify the time required to open and close the 
        shutter (this information is required for calculating acquisition 
        timings – see SHUTTER TRANSFER TIME).
        typ:    0 Output TTL low signal to open shutter 
                1 Output TTL high signal to open shutter
        mode:   0 Fully Auto 
                1 Permanently Open 
                2 Permanently Closed 
                4 Open for FVB series 
                5 Open for any series
        closingtime and openingtime are in milliseconds."""
    return None


@uint_winapi([ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int])
def SetShutterEx(typ, mode, closingtime, openingtime, extmode):
    """This function expands the control offered by SetShutter to allow an 
        external shutter and internal shutter to be controlled independently 
        (only available on some cameras – please consult your Camera User 
        Guide). The typ parameter allows the user to control the TTL signal 
        output to an external shutter. The opening and closing times specify 
        the length of time required to open and close the shutter (this 
        information is required for calculating acquisition timings – see 
        SHUTTER TRANSFER TIME). The mode and extmode parameters control the 
        behaviour of the internal and external shutters. To have an external 
        shutter open and close automatically in an experiment, set the mode 
        parameter to “Open” and set the extmode parameter to “Auto”. To have 
        an internal shutter open and close automatically in an experiment, 
        set the extmode parameter to “Open” and set the mode parameter to 
        “Auto”. To not use any shutter in the experiment, set both shutter 
        modes to permanently open. """
    return None


@uint_winapi([ctypes.c_int])
def SetTriggerMode(mode):
    """ This function will set the trigger mode that the camera will 
        operate in. 
        Valid values:   0. Internal 
                        1. External 
                        6. External Start 
                        7. External Exposure (Bulb)
                        9. External FVB EM (only valid for EM Newton models 
                                            in FVB mode) 
                        10. Software Trigger 
                        12. External Charge Shifting """
    return None


@uint_winapi([ctypes.c_int])
def SetFastExtTrigger(mode):
    """This function will enable fast external triggering. When fast external 
    triggering is enabled the system will NOT wait until a “Keep Clean” cycle 
    has been completed before accepting the next trigger. This setting will only 
    have an effect if the trigger mode has been set to External via SetTriggerMode.
    int mode: 0 Disabled 
              1 Enabled
    """
    return None

@uint_winapi(
    [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
)
def SetImage(hbin, vbin, hstart, hend, vstart, vend):
    """ This function will set the horizontal and vertical binning to be 
        used when taking a full resolution image."""
    return None

@uint_winapi()
def StartAcquisition():
    """ This function starts an acquisition. The status of the acquisition 
        can be monitored via GetStatus(). """
    return None

def GetStatus():
    """ This function will return the current status of the Andor SDK system. 
        This function should be called before an acquisition is started to 
        ensure that it is IDLE and during an acquisition to monitor the 
        process. 
        Wrapped function returns code message. """
    andor_solis.GetStatus.restype = ctypes.c_uint
    status = ctypes.c_int()
    result = andor_solis.GetStatus(ctypes.byref(status))
    check_status(result)
    return str(_SC[int(status.value)])

def GetReadOutTime():
    """ This function will return the time to readout data from a sensor. 
        This function should be used after all the acquisitions settings 
        have been set, e.g. SetExposureTime, SetKineticCycleTime and 
        SetReadMode etc. The value returned is the actual times used in 
        subsequent acquisitions."""
    andor_solis.GetReadOutTime.restype = ctypes.c_uint
    ReadoutTime = ctypes.c_float()
    result = andor_solis.GetReadOutTime(ctypes.byref(ReadoutTime))
    check_status(result)
    return float(ReadoutTime.value)

def GetKeepCleanTime():
    """ This function will return the time to perform a keep clean cycle. 
    This function should be used after all the acquisitions settings have been set, 
    e.g. SetExposureTime, SetKineticCycleTime and SetReadMode etc. The value 
    returned is the actual times used in subsequent acquisitions."""
    andor_solis.GetKeepCleanTime.restype = ctypes.c_uint
    KeepCleanTime = ctypes.c_float()
    result = andor_solis.GetKeepCleanTime(ctypes.byref(KeepCleanTime))
    check_status(result)
    return float(KeepCleanTime.value)

@uint_winapi()
def WaitForAcquisition():
    """ WaitForAcquisition can be called after an acquisition is started 
        using StartAcquisition to put the calling thread to sleep until
        an Acquisition Event occurs. This can be used as a simple alternative 
        to the functionality provided by the SetDriverEvent function, as 
        all Event creation and handling is performed internally by the SDK 
        library. Like the SetDriverEvent functionality it will use less
        processor resources than continuously polling with the GetStatus 
        function. If you wish to restart the calling thread without waiting 
        for an Acquisition event, call the function CancelWait. An Acquisition 
        Event occurs each time a new image is acquired during an Accumulation, 
        Kinetic Series or Run-Till-Abort acquisition or at the end of a Single 
        Scan Acquisition. If a second event occurs before the first one has 
        been acknowledged, the first one will be ignored. Care should be taken 
        in this case, as you may have to use CancelWait to exit the function."""
    return None


def IsInternalMechanicalShutter():
    """ This function checks if an iXon camera has a mechanical shutter 
        installed. 
            0: Mechanical shutter not installed.
            1: Mechanical shutter installed. """
    andor_solis.IsInternalMechanicalShutter.restype = ctypes.c_uint
    InternalShutter = ctypes.c_int()
    result = andor_solis.IsInternalMechanicalShutter(ctypes.byref(InternalShutter))
    check_status(result)
    return int(InternalShutter.value)


@uint_winapi(
    [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_float,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
    ]
)
def SetFastKinetics(exposedRows, seriesLength, time, mode, hbin, vbin):
    """ This function will set the parameters to be used when taking a fast
        kinetics acquisition. """
    return None


@uint_winapi(
    [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_float,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
    ]
)
def SetFastKineticsEx(exposedRows, seriesLength, time, mode, hbin, vbin, offset):
    """ This function is the same as SetFastKinetics with the addition of an 
        Offset parameter, which will inform the SDK of the first row to be 
        used."""
    return None


@uint_winapi([ctypes.c_int])
def SetFKVShiftSpeed(index):
    """This function will set the fast kinetics vertical shift speed to one 
        of the possible speeds of the system. It will be used for subsequent 
        acquisitions.
        index:    Valid values: 0 to GetNumberFKVShiftSpeeds-1 """
    return None

@uint_winapi([ctypes.c_int])
def SetFrameTransferMode(mode):
    """This function will set whether an acquisition will readout in Frame Transfer Mode. If the
        acquisition mode is Single Scan or Fast Kinetics this call will have no affect.

        mode:    0 OFF; 1 ON"""
    
    return None

def GetNumberFKVShiftSpeeds():
    """ As your Andor SDK system is capable of operating at more than one 
        fast kinetics vertical shift speed this function will return the 
        actual number of speeds available."""
    andor_solis.GetNumberFKVShiftSpeeds.restype = ctypes.c_uint
    number = ctypes.c_int()
    result = andor_solis.GetNumberFKVShiftSpeeds(ctypes.byref(number))
    check_status(result)
    return int(number.value)

def GetFKVShiftSpeedF(index):
    """ As your Andor system is capable of operating at more than one fast 
        kinetics vertical shift speed this function will return the actual 
        speeds available. The value returned is in microseconds per pixel 
        shift. 
        index:  Valid values: 0 to GetNumberFKVShiftSpeeds()-1. """
    andor_solis.GetFKVShiftSpeedF.restype = ctypes.c_uint
    speed = ctypes.c_float()
    result = andor_solis.GetFKVShiftSpeedF(ctypes.c_int(index), ctypes.byref(speed))
    check_status(result)
    return float(speed.value)

def GetFKExposureTime():
    """ This function will return the current “valid” exposure time for a 
        fast kinetics acquisition. This function should be used after all 
        the acquisitions settings have been set, i.e. SetFastKinetics and 
        SetFKVShiftSpeed. The value returned is the actual time used in 
        subsequent acquisitions."""
    andor_solis.GetFKExposureTime.restype = ctypes.c_uint
    time = ctypes.c_float()  # In seconds
    result = andor_solis.GetFKExposureTime(ctypes.byref(time))
    check_status(result)
    return float(time.value)


def GetNumberAvailableImages():
    """ This function will return information on the number of available 
        images in the circular buffer. This information can be used with 
        GetImages to retrieve a series of images. If any images are 
        overwritten in the circular buffer they no longer can be retrieved
        and the information returned will treat overwritten images as not 
        available. """
    andor_solis.GetNumberAvailableImages.restype = ctypes.c_uint
    first = ctypes.c_long()
    last = ctypes.c_long()
    result = andor_solis.GetNumberAvailableImages(
        ctypes.byref(first), ctypes.byref(last)
    )
    check_status(result)
    return int(first.value), int(last.value)

def GetImages(first, last, shape):
    """ This function will update the data array with the specified series 
        of images from the circular buffer. If the specified series is out of
        range (i.e. the images have been overwritten or have not yet been 
        acquired then an error will be returned. """
    andor_solis.GetImages.restype = ctypes.c_uint
    arr = (ctypes.c_long * shape[0] * shape[1])()
    size = shape[0] * shape[1] * int(abs(last - first))
    validfirst = ctypes.c_long()
    validlast = ctypes.c_long()
    result = andor_solis.GetImages(
        ctypes.c_long(first),
        ctypes.c_long(last),
        ctypes.pointer(arr[0]),
        ctypes.c_ulong(size),
        ctypes.byref(validfirst),
        ctypes.byref(validlast),
    )
    check_status(result)
    return np.ctypeslib.as_array(arr)

def GetMostRecentImage(shape):
    """ This function will update the data array with the most recently 
        acquired image in any acquisition mode. The data are returned as 
        long integers (32-bit signed integers). The "array" must be exactly 
        the same size as the complete image."""
    andor_solis.GetMostRecentImage.restype = ctypes.c_uint
    arr = (ctypes.c_long * shape[1] * shape[0])()
    size = shape[0] * shape[1]
    result = andor_solis.GetMostRecentImage(
        ctypes.pointer(arr[0]), ctypes.c_ulong(size)
    )
    check_status(result)
    return np.ctypeslib.as_array(arr)


def GetOldestImage(shape):
    """ This function will update the data array with the oldest image in the 
        circular buffer. Once the oldest image has been retrieved it no longer is 
        available. The data are returned as long integers (32-bit signed integers). 
        The "array" must be exactly the same size as the full image."""
    andor_solis.GetOldestImage.restype = ctypes.c_uint
    size = np.prod(shape)
    arr = (ctypes.c_int32 * size)()
    result = andor_solis.GetOldestImage(ctypes.pointer(arr), ctypes.c_ulong(size))
    check_status(result)
    return np.ctypeslib.as_array(arr)


def GetOldestImage16(shape):
    """ This function will update the data array with the oldest image in the 
    circular buffer. Once the oldest image has been retrieved it no longer is 
    available. The data are returned as long integers (32-bit signed integers). 
    The "array" must be exactly the same size as the full image."""
    andor_solis.GetOldestImage.restype = ctypes.c_uint
    size = np.prod(shape)
    arr = (ctypes.c_int16 * size)()
    result = andor_solis.GetOldestImage16(ctypes.pointer(arr), ctypes.c_ulong(size))
    check_status(result)
    return np.ctypeslib.as_array(arr)


@uint_winapi([ctypes.c_int])
def SetFanMode(mode):
    """ Allows the user to control the mode of the camera fan. If the system 
        is cooled, the fan should only be turned off for short periods of 
        time. During this time the body of the camera will warm up which 
        could compromise cooling capabilities. If the camera body reaches too 
        high a temperature, depends on camera, the buzzer will sound. If this 
        happens, turn off the external power supply and allow the system to 
        stabilize before continuing. 
        Values: fan on full (0) fan on low (1) fan off (2)"""
    return None


def GetEMGainRange():
    """ Returns the minimum and maximum values of the current selected EM 
        Gain mode and temperature of the sensor. """
    andor_solis.GetEMGainRange.restype = ctypes.c_uint
    low, high = ctypes.c_int(), ctypes.c_int()
    result = andor_solis.GetEMGainRange(ctypes.byref(low), ctypes.byref(high))
    check_status(result)
    return int(low.value), int(high.value)

def GetTemperatureRange():
    """ This function returns the valid range of temperatures in centigrade 
        to which the detector can be cooled. """
    andor_solis.GetTemperatureRange.restype = ctypes.c_uint
    mintemp, maxtemp = ctypes.c_int(), ctypes.c_int()
    result = andor_solis.GetTemperatureRange(
        ctypes.byref(mintemp), ctypes.byref(maxtemp)
    )
    check_status(result)
    return int(mintemp.value), int(maxtemp.value)

@uint_winapi([ctypes.c_int])
def SetTriggerInvert(mode):
    """ This function will set whether an acquisition will be triggered on 
        a rising or falling edge external trigger. \n
        Parameters:
            int mode: trigger mode 
        Valid values:
            0. Rising Edge 
            1. Falling Edge. 
    """
    return None


@uint_winapi([ctypes.c_int])
def SetTemperature(temperature):
    """This function will set the desired temperature of the detector. 
        To turn the cooling ON and OFF use the CoolerON and CoolerOFF 
        function respectively."""
    return None


def GetTemperature():
    """This function returns the temperature of the detector to the 
        nearest degree. It also gives the status of cooling process."""
    andor_solis.GetTemperature.restype = ctypes.c_uint
    temperature = ctypes.c_int()
    result = andor_solis.GetTemperature(ctypes.byref(temperature))
    check_status(result)
    status = _SC[result]
    return int(temperature.value), str(status)


def GetTemperatureF():
    """ This function returns the temperature in degrees of the detector. 
        It also gives the status of cooling process."""
    andor_solis.GetTemperatureF.restype = ctypes.c_uint
    temperature = ctypes.c_float()
    result = andor_solis.GetTemperatureF(ctypes.byref(temperature))
    check_status(result)
    status = _SC[result]
    return float(temperature.value), str(status)


@uint_winapi([ctypes.c_int])
def SetEMGainMode(mode):
    """ Set the EM Gain mode to one of the following possible settings. 
        Mode  (0 is default)
            0: The EM Gain is controlled by DAC settings in the range 0-255. 
            1: The EM Gain is controlled by DAC settings in the range 0-4095.
            2: Linear mode.
            3: Real EM gain
        To access higher gain values (if available) it is necessary to enable 
        advanced EM gain, see SetEMAdvanced."""
    return None


@uint_winapi([ctypes.c_int])
def SetEMCCDGain(gain):
    """ Allows the user to change the gain value. The valid range for the 
        gain depends on what gain mode the camera is operating in. See 
        SetEMGainMode to set the mode and GetEMGainRange to get the valid 
        range to work with. To access higher gain values (>x300) see 
        SetEMAdvanced. """
    return None


def GetEMCCDGain():
    """ Returns the current gain setting. The meaning of the value returned 
        depends on the EM Gain mode."""
    andor_solis.GetEMCCDGain.restype = ctypes.c_uint
    gain = ctypes.c_int()
    result = andor_solis.GetEMCCDGain(ctypes.byref(gain))
    check_status(result)
    return int(gain.value)


@uint_winapi([ctypes.c_int])
def SetCoolerMode(mode):
    """ This function determines whether the cooler is switched off when 
        the camera is shut down.
        1 – Temperature is maintained on ShutDown
        0 – Returns to ambient temperature on ShutDown"""
    return None


def GetPixelSize():
    """ This function returns the dimension of the pixels in the detector 
        in microns. """
    andor_solis.GetPixelSize.restype = ctypes.c_uint
    xSize, ySize = ctypes.c_float(), ctypes.c_float()
    result = andor_solis.GetPixelSize(ctypes.byref(xSize), ctypes.byref(ySize))
    check_status(result)
    return float(xSize.value), float(ySize.value)


def GetNumberPreAmpGains():
    """ Available in some systems are a number of pre amp gains that can 
        be applied to the data as it is read out. This function gets the 
        number of these pre amp gains available. The functions GetPreAmpGain 
        and SetPreAmpGain can be used to specify which of these gains is 
        to be used. """
    andor_solis.GetNumberPreAmpGains.restype = ctypes.c_uint
    noGains = ctypes.c_int()
    result = andor_solis.GetNumberPreAmpGains(ctypes.byref(noGains))
    check_status(result)
    return int(noGains.value)


def GetPreAmpGain(index):
    """ For those systems that provide a number of pre amp gains to apply 
        to the data as it is read out; this function retrieves the amount 
        of gain that is stored for a particular index. The number of gains 
        available can be obtained by calling the GetNumberPreAmpGains function 
        and a specific Gain can be selected using the function 
        SetPreAmpGain. """
    andor_solis.GetPreAmpGain.restype = ctypes.c_uint
    gain = ctypes.c_float()
    result = andor_solis.GetPreAmpGain(ctypes.c_int(index), ctypes.byref(gain))
    check_status(result)
    return float(gain.value)


@uint_winapi([ctypes.c_int])
def SetPreAmpGain(index):
    """ This function will set the pre amp gain to be used for subsequent 
        acquisitions. The actual gain factor that will be applied can be 
        found through a call to the GetPreAmpGain function. The number of 
        Pre Amp Gains available is found by calling the GetNumberPreAmpGains
        function. """
    return None


@uint_winapi([ctypes.c_int])
def SetNumberKinetics(number):
    """ This function will set the number of scans (possibly accumulated scans) 
    to be taken during a single acquisition sequence. This will only take effect 
    if the acquisition mode is Kinetic Series."""
    return None


@uint_winapi([ctypes.c_float])
def SetKineticCycleTime(time):
    """ This function will set the kinetic cycle time to the nearest valid value 
    not less than the given value. The actual time used is obtained by 
    GetAcquisitionTimings. Please refer to SECTION 5 – ACQUISITION MODES for 
    further information. """
    return None


@uint_winapi([ctypes.c_int])
def SetNumberAccumulations(number):
    """ This function will set the number of scans accumulated in memory. This
    will only take effect if the acquisition mode is either Accumulate or Kinetic 
    Series. """
    return None


@uint_winapi([ctypes.c_float])
def SetAccumulationCycleTime(time):
    """ This function will set the accumulation cycle time to the nearest valid 
    value not less than the given value. The actual cycle time used is obtained 
    by GetAcquisitionTimings."""
    return None


@uint_winapi([ctypes.c_int])
def WaitForAcquisitionTimeOut(timeout_ms):
    """WaitForAcquisitionTimeOut can be called after an acquisition is started 
    using StartAcquisition to put the calling thread to sleep until an Acquisition 
    Event occurs. This can be used as a simple alternative to the functionality 
    provided by the SetDriverEvent function, as all Event creation and handling 
    is performed internally by the SDK library. Like the SetDriverEvent 
    functionality it will use less processor resources than continuously polling 
    with the GetStatus function. If you wish to restart the calling thread 
    without waiting for an Acquisition event, call the function CancelWait. An 
    Acquisition Event occurs each time a new image is acquired during an 
    Accumulation, Kinetic Series or Run-Till-Abort acquisition or at the end 
    of a Single Scan Acquisition. If an Acquisition Event does not occur 
    within _TimeOutMs milliseconds, WaitForAcquisitionTimeOut returns 
    DRV_NO_NEW_DATA"""
    return None
