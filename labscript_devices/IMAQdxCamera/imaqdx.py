#####################################################################
#                                                                   #
# /labscript_devices/IMAQdxCamera/imaqdx.py                         #
#                                                                   #
# Copyright 2026, Christopher Billington                            #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
"""ctypes bindings for the NI-IMAQdx and NI Vision functions that :obj:`IMAQdx_Camera
<labscript_devices.IMAQdxCamera.blacs_workers.IMAQdx_Camera>` calls.

The libraries are installed by NI Vision Acquisition Software. The names and arguments
are those of the C functions in ``NIIMAQdx.h`` and ``nivision.h``, except that strings
are ``str``, and output arguments are return values. A nonzero status from an IMAQdx
function raises :obj:`IMAQdxError`, and a failed NI Vision function raises
:obj:`ImaqError`.
"""

import ctypes
import sys
from ctypes import POINTER, Structure, byref, c_char, c_char_p, c_double, c_int
from ctypes import c_int64, c_uint32, c_void_p

import numpy as np

if sys.platform == 'win32':
    _imaqdx = ctypes.WinDLL('niimaqdx')
    _nivision = ctypes.WinDLL('nivision')
else:
    _imaqdx = ctypes.CDLL('libniimaqdx.so')
    _nivision = ctypes.CDLL('libnivision.so')

bool32 = c_uint32
IMAQdxSession = c_uint32

IMAQDX_MAX_API_STRING_LENGTH = 512

IMAQdxCameraControlModeController = 0

IMAQdxAttributeTypeU32 = 0
IMAQdxAttributeTypeI64 = 1
IMAQdxAttributeTypeF64 = 2
IMAQdxAttributeTypeString = 3
IMAQdxAttributeTypeEnum = 4
IMAQdxAttributeTypeBool = 5
IMAQdxAttributeTypeCommand = 6
IMAQdxAttributeTypeBlob = 7

IMAQdxValueTypeU32 = 0
IMAQdxValueTypeI64 = 1
IMAQdxValueTypeF64 = 2
IMAQdxValueTypeString = 3
IMAQdxValueTypeEnumItem = 4
IMAQdxValueTypeBool = 5
IMAQdxValueTypeDisposableString = 6

IMAQdxAttributeVisibilitySimple = 0x00001000
IMAQdxAttributeVisibilityIntermediate = 0x00002000
IMAQdxAttributeVisibilityAdvanced = 0x00004000

IMAQdxErrorTimeout = 0xBFF6901B

IMAQ_IMAGE_U16 = 7


class IMAQdxCameraInformation(Structure):
    _fields_ = [
        ('Type', c_uint32),
        ('Version', c_uint32),
        ('Flags', c_uint32),
        ('SerialNumberHi', c_uint32),
        ('SerialNumberLo', c_uint32),
        ('BusType', c_uint32),
        ('InterfaceName', c_char * IMAQDX_MAX_API_STRING_LENGTH),
        ('VendorName', c_char * IMAQDX_MAX_API_STRING_LENGTH),
        ('ModelName', c_char * IMAQDX_MAX_API_STRING_LENGTH),
        ('CameraFileName', c_char * IMAQDX_MAX_API_STRING_LENGTH),
        ('CameraAttributeURL', c_char * IMAQDX_MAX_API_STRING_LENGTH),
    ]


class IMAQdxAttributeInformation(Structure):
    _fields_ = [
        ('Type', c_uint32),
        ('Readable', bool32),
        ('Writable', bool32),
        ('Name', c_char * IMAQDX_MAX_API_STRING_LENGTH),
    ]


class IMAQdxEnumItem(Structure):
    _fields_ = [
        ('Value', c_uint32),
        ('Reserved', c_uint32),
        ('Name', c_char * IMAQDX_MAX_API_STRING_LENGTH),
    ]


class Rect(Structure):
    _fields_ = [('top', c_int), ('left', c_int), ('height', c_int), ('width', c_int)]


IMAQ_NO_RECT = Rect(0, 0, 0x7FFFFFFF, 0x7FFFFFFF)


class IMAQdxError(Exception):
    """An IMAQdx function returned the nonzero status `code`."""

    def __init__(self, code):
        self.code = code
        message = ctypes.create_string_buffer(256)
        _IMAQdxGetErrorString(code, message, len(message))
        super().__init__(f'0x{code:08X}: {message.value.decode("utf8", "replace")}')


class ImaqError(Exception):
    """An NI Vision function failed. `code` is the NI Vision error code."""

    def __init__(self):
        self.code = _imaqGetLastError()
        text = _imaqGetErrorText(self.code)
        if text:
            message = ctypes.string_at(text).decode('utf8', 'replace')
            _imaqDispose(text)
        else:
            message = 'Unknown error'
        super().__init__(f'{self.code}: {message}')


def _check_imaqdx(status, function, arguments):
    if status:
        raise IMAQdxError(status)
    return status


def _check_imaq(result, function, arguments):
    if not result:
        raise ImaqError()
    return result


def _declare(library, name, restype, argtypes, errcheck=None):
    # Indexing the library, unlike attribute access, makes a new function object, so
    # that IMAQdxSetAttribute can be declared once for each type of its last argument:
    function = library[name]
    function.restype = restype
    function.argtypes = argtypes
    if errcheck is not None:
        function.errcheck = errcheck
    return function


def _imaqdx_function(name, *argtypes):
    return _declare(_imaqdx, name, c_uint32, argtypes, _check_imaqdx)


_IMAQdxGetErrorString = _declare(
    _imaqdx, 'IMAQdxGetErrorString', c_uint32, (c_uint32, c_char_p, c_uint32)
)
_imaqGetLastError = _declare(_nivision, 'imaqGetLastError', c_int, ())
_imaqGetErrorText = _declare(_nivision, 'imaqGetErrorText', c_void_p, (c_int,))
_imaqDispose = _declare(_nivision, 'imaqDispose', c_int, (c_void_p,))

_IMAQdxEnumerateCameras = _imaqdx_function(
    'IMAQdxEnumerateCameras', POINTER(IMAQdxCameraInformation), POINTER(c_uint32), bool32
)
_IMAQdxOpenCamera = _imaqdx_function(
    'IMAQdxOpenCamera', c_char_p, c_uint32, POINTER(IMAQdxSession)
)
IMAQdxCloseCamera = _imaqdx_function('IMAQdxCloseCamera', IMAQdxSession)
IMAQdxConfigureAcquisition = _imaqdx_function(
    'IMAQdxConfigureAcquisition', IMAQdxSession, bool32, c_uint32
)
IMAQdxStartAcquisition = _imaqdx_function('IMAQdxStartAcquisition', IMAQdxSession)
IMAQdxStopAcquisition = _imaqdx_function('IMAQdxStopAcquisition', IMAQdxSession)
IMAQdxUnconfigureAcquisition = _imaqdx_function(
    'IMAQdxUnconfigureAcquisition', IMAQdxSession
)
IMAQdxSnap = _imaqdx_function('IMAQdxSnap', IMAQdxSession, c_void_p)
_IMAQdxGrab = _imaqdx_function(
    'IMAQdxGrab', IMAQdxSession, c_void_p, bool32, POINTER(c_uint32)
)
_IMAQdxGetAttributeType = _imaqdx_function(
    'IMAQdxGetAttributeType', IMAQdxSession, c_char_p, POINTER(c_uint32)
)
_IMAQdxGetAttribute = _imaqdx_function(
    'IMAQdxGetAttribute', IMAQdxSession, c_char_p, c_uint32, c_void_p
)
# IMAQdxSetAttribute is variadic, with a last argument of the given value type:
_IMAQdxSetAttribute = {
    value_ctype: _imaqdx_function(
        'IMAQdxSetAttribute', IMAQdxSession, c_char_p, c_uint32, value_ctype
    )
    for value_ctype in [c_uint32, c_int64, c_double, c_char_p]
}
_IMAQdxEnumerateAttributes2 = _imaqdx_function(
    'IMAQdxEnumerateAttributes2',
    IMAQdxSession,
    POINTER(IMAQdxAttributeInformation),
    POINTER(c_uint32),
    c_char_p,
    c_uint32,
)

imaqCreateImage = _declare(
    _nivision, 'imaqCreateImage', c_void_p, (c_uint32, c_int), _check_imaq
)
_imaqImageToArray = _declare(
    _nivision,
    'imaqImageToArray',
    c_void_p,
    (c_void_p, Rect, POINTER(c_int), POINTER(c_int)),
    _check_imaq,
)
_imaqGetBytesPerPixel = _declare(
    _nivision, 'imaqGetBytesPerPixel', c_int, (c_void_p, POINTER(c_int)), _check_imaq
)
imaqDispose = _declare(_nivision, 'imaqDispose', c_int, (c_void_p,), _check_imaq)


def IMAQdxEnumerateCameras(connectedOnly):
    """Return a list of IMAQdxCameraInformation"""
    count = c_uint32()
    _IMAQdxEnumerateCameras(None, byref(count), connectedOnly)
    cameras = (IMAQdxCameraInformation * count.value)()
    _IMAQdxEnumerateCameras(cameras, byref(count), connectedOnly)
    return cameras[: count.value]


def IMAQdxOpenCamera(name, mode):
    """Return the session ID"""
    session = IMAQdxSession()
    _IMAQdxOpenCamera(name.encode('utf8'), mode, byref(session))
    return session.value


def IMAQdxGrab(id, image, waitForNextBuffer):
    """Return the number of the buffer that was copied into the image"""
    actualBufferNumber = c_uint32()
    _IMAQdxGrab(id, image, waitForNextBuffer, byref(actualBufferNumber))
    return actualBufferNumber.value


def IMAQdxGetAttributeType(id, name):
    attribute_type = c_uint32()
    _IMAQdxGetAttributeType(id, name.encode('utf8'), byref(attribute_type))
    return attribute_type.value


def IMAQdxGetAttribute(id, name):
    """Return the value of an attribute as an int, float, str or bool. The value of an
    enumeration attribute is the name of its item."""
    attribute_type = IMAQdxGetAttributeType(id, name)
    encoded_name = name.encode('utf8')
    if attribute_type == IMAQdxAttributeTypeString:
        value = ctypes.create_string_buffer(IMAQDX_MAX_API_STRING_LENGTH)
        _IMAQdxGetAttribute(id, encoded_name, IMAQdxValueTypeString, value)
        return value.value.decode('utf8')
    if attribute_type == IMAQdxAttributeTypeEnum:
        item = IMAQdxEnumItem()
        _IMAQdxGetAttribute(id, encoded_name, IMAQdxValueTypeEnumItem, byref(item))
        return item.Name.decode('utf8')
    value_types = {
        IMAQdxAttributeTypeU32: (IMAQdxValueTypeU32, c_uint32),
        IMAQdxAttributeTypeI64: (IMAQdxValueTypeI64, c_int64),
        IMAQdxAttributeTypeF64: (IMAQdxValueTypeF64, c_double),
        IMAQdxAttributeTypeBool: (IMAQdxValueTypeBool, bool32),
    }
    if attribute_type not in value_types:
        raise TypeError(f"attribute {name} has type {attribute_type}, not a value")
    value_type, value_ctype = value_types[attribute_type]
    value = value_ctype()
    _IMAQdxGetAttribute(id, encoded_name, value_type, byref(value))
    if attribute_type == IMAQdxAttributeTypeBool:
        return bool(value.value)
    return value.value


def IMAQdxSetAttribute(id, name, value):
    """Set an attribute to an int, float, str or bool. An enumeration attribute takes
    the name or the value of an item."""
    attribute_type = IMAQdxGetAttributeType(id, name)
    encoded_name = name.encode('utf8')
    if attribute_type == IMAQdxAttributeTypeU32:
        value_type, value_ctype, value = IMAQdxValueTypeU32, c_uint32, int(value)
    elif attribute_type == IMAQdxAttributeTypeI64:
        value_type, value_ctype, value = IMAQdxValueTypeI64, c_int64, int(value)
    elif attribute_type == IMAQdxAttributeTypeF64:
        value_type, value_ctype, value = IMAQdxValueTypeF64, c_double, float(value)
    elif attribute_type == IMAQdxAttributeTypeBool:
        value_type, value_ctype, value = IMAQdxValueTypeBool, bool32, int(value)
    elif attribute_type == IMAQdxAttributeTypeEnum and isinstance(value, int):
        value_type, value_ctype = IMAQdxValueTypeU32, c_uint32
    elif attribute_type in (IMAQdxAttributeTypeString, IMAQdxAttributeTypeEnum):
        value_type, value_ctype = IMAQdxValueTypeString, c_char_p
        value = str(value).encode('utf8')
    else:
        raise TypeError(f"attribute {name} has type {attribute_type}, not a value")
    _IMAQdxSetAttribute[value_ctype](id, encoded_name, value_type, value)


def IMAQdxEnumerateAttributes2(id, root, visibility):
    """Return a list of IMAQdxAttributeInformation"""
    count = c_uint32()
    root = root.encode('utf8')
    _IMAQdxEnumerateAttributes2(id, None, byref(count), root, visibility)
    attributes = (IMAQdxAttributeInformation * count.value)()
    _IMAQdxEnumerateAttributes2(id, attributes, byref(count), root, visibility)
    return attributes[: count.value]


def imaqImageToArray(image):
    """Return a copy of the pixels of an image as a 2D array of shape (rows, columns)"""
    columns = c_int()
    rows = c_int()
    pixels = _imaqImageToArray(image, IMAQ_NO_RECT, byref(columns), byref(rows))
    try:
        byte_count = c_int()
        _imaqGetBytesPerPixel(image, byref(byte_count))
        dtype = {1: np.uint8, 2: np.uint16, 4: np.uint32}[byte_count.value]
        array = np.empty((rows.value, columns.value), dtype=dtype)
        ctypes.memmove(array.ctypes.data, pixels, array.nbytes)
        return array
    finally:
        imaqDispose(pixels)
