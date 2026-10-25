#####################################################################
#                                                                   #
# /labscript_devices/usbserial.py                                   #
#                                                                   #
# Copyright 2026, Christopher Billington                            #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
"""A wrapper around pyserial for USB-serial adaptors that sets the latency timer of FTDI
adaptors to 1 ms and implements read timeouts in software.

An FTDI adaptor holds received data for up to its latency timer before sending it to the
computer, 16 ms by default, so every reply from a device takes at least that long. On
Linux the low-latency mode of the ``ftdi_sio`` driver sets the timer to 1 ms. On Windows
the timer can only be set through FTDI's D2XX library, which Windows normally installs
with FTDI's driver when an FTDI adaptor is first plugged in, so for FTDI adaptors
:func:`Serial` uses D2XX instead of the virtual COM port driver. On macOS the latency
timer is not changed.
"""

import ctypes
import os
import sys
import threading
import time
import warnings
import weakref

import serial
from serial.tools.list_ports import comports

_LINUX = sys.platform.startswith('linux')
_WINDOWS = sys.platform == 'win32'

_FTDI_VENDOR_ID = 0x0403

_FTD2XX_WARNING = """FTDI D2XX library not found. Serial communication with FTDI
adaptors will have up to 16 ms of added latency. The D2XX library is available from
https://ftdichip.com/drivers/d2xx-drivers/"""

if _WINDOWS:
    try:
        _ftd2xx = ctypes.WinDLL("ftd2xx.dll")
    except OSError:
        _ftd2xx = None
else:
    _ftd2xx = None


def _get_usb_info(port):
    """The USB vendor ID, product ID and product string of a serial port, or None if
    the port is not a USB device that pyserial lists."""
    if not _WINDOWS:
        port = os.path.realpath(port)
    for p in comports():
        if p.device == port and p.vid is not None:
            return p.vid, p.pid, p.product
    return None


def _d2xx_open(port, vid, pid):
    """Find the D2XX device with USB IDs `vid` and `pid` that has the COM port `port`
    by opening each device with these IDs and reading its COM port number. Devices of
    one product can share a serial number, so the serial number does not identify a
    device. Returns the open handle of the device or None, its description, and the
    descriptions of the devices with these IDs that this process could not open. A
    device that another process has open is not among them, since D2XX does not
    report its IDs."""
    n = ctypes.c_ulong()
    if _ftd2xx.FT_CreateDeviceInfoList(ctypes.byref(n)) != 0:
        return None, None, []
    number = int(port[3:])
    in_use = []
    for i in range(n.value):
        flags, dev_type, dev_id, location = (ctypes.c_ulong() for _ in range(4))
        sn = ctypes.create_string_buffer(16)
        description = ctypes.create_string_buffer(64)
        handle = ctypes.c_void_p()
        rc = _ftd2xx.FT_GetDeviceInfoDetail(
            i,
            ctypes.byref(flags),
            ctypes.byref(dev_type),
            ctypes.byref(dev_id),
            ctypes.byref(location),
            sn,
            description,
            ctypes.byref(handle),
        )
        if rc != 0 or dev_id.value != (vid << 16) | pid:
            continue
        description = description.value.decode(errors='replace')
        if _ftd2xx.FT_Open(i, ctypes.byref(handle)) != 0:
            in_use.append(description)
            continue
        com = ctypes.c_long()
        if _ftd2xx.FT_GetComPortNumber(handle, ctypes.byref(com)) == 0 and com.value == number:
            return handle, description, in_use
        _ftd2xx.FT_Close(handle)
    return None, None, in_use


def usb_product(port):
    """The USB product string of the adaptor of a serial port, or None if it is not
    known.

    On Windows, for an FTDI adaptor when D2XX is installed, this is the description that
    D2XX reports, which for a device with more than one channel is the product string,
    a space and the channel letter. If the port is in use, the description is known only
    if every device with the same USB IDs that is in use has the same description.
    Without D2XX, it is None on Windows."""
    usb_info = _get_usb_info(port)
    if usb_info is None:
        return None
    vid, pid, product = usb_info
    if _WINDOWS and vid == _FTDI_VENDOR_ID and _ftd2xx is not None:
        handle, description, in_use = _d2xx_open(port, vid, pid)
        if handle is not None:
            _ftd2xx.FT_Close(handle)
            return description
        if len(set(in_use)) == 1:
            return in_use[0]
        return None
    return product


def _set_low_latency_serial_linux(fd):
    """Enable low-latency mode on a Linux serial port, which sets the latency timer of an
    FTDI adaptor to 1 ms. Does nothing if the mode is already enabled, since enabling it
    again delays the next read by up to 255 ms."""
    import array
    import fcntl
    import termios

    ASYNC_LOW_LATENCY_WORD = 4
    ASYNC_LOW_LATENCY_MASK = 0x2000

    buf = array.array('i', [0] * 32)
    try:
        fcntl.ioctl(fd, termios.TIOCGSERIAL, buf)
        if buf[ASYNC_LOW_LATENCY_WORD] & ASYNC_LOW_LATENCY_MASK:
            return
        buf[ASYNC_LOW_LATENCY_WORD] |= ASYNC_LOW_LATENCY_MASK
        fcntl.ioctl(fd, termios.TIOCSSERIAL, buf)
    except OSError:
        # Not supported by the driver
        return
    # When the latency timer is reduced, it may not fire for up to 255 ms, the largest
    # value that it can have. We wait for this time so that the caller's read timeouts
    # do not have to allow for it.
    time.sleep(0.255)



if _WINDOWS:
    from ctypes import wintypes

    _kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    _kernel32.CreateEventW.restype = wintypes.HANDLE
    _kernel32.CreateEventW.argtypes = [
        ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR
    ]
    _kernel32.SetEvent.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.WaitForSingleObject.restype = wintypes.DWORD
    _kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    _kernel32.WaitForMultipleObjects.restype = wintypes.DWORD
    _kernel32.WaitForMultipleObjects.argtypes = [
        wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE), wintypes.BOOL, wintypes.DWORD
    ]
    _WAIT_OBJECT_0 = 0
    _WAIT_TIMEOUT = 0x102
    _INFINITE = 0xFFFFFFFF


# Distinguishes timeout=None from no timeout argument to read():
_UNSET = object()


class _BreakMixin:
    # pyserial's send_break() on Linux calls tcsendbreak() as if its argument were in
    # units of 0.25 s, but Linux takes milliseconds and rounds up to 100 ms; macOS ignores
    # the argument. Toggling the break condition with a sleep, as pyserial does on
    # Windows, works on every platform.
    def send_break(self, duration=0.25):
        if not self.is_open:
            raise serial.PortNotOpenError()
        try:
            self.break_condition = True
            time.sleep(duration)
        finally:
            self.break_condition = False


class _FTD2xxSerial(_BreakMixin):
    """A serial port opened through FTDI's D2XX library instead of the virtual COM port
    driver, with the latency timer set to 1 ms. The port is always opened exclusively.

    A read calls the D2XX read function only for bytes that have already been received,
    and otherwise waits on the event that D2XX sets when data arrives, since a D2XX write
    from another thread waits until a D2XX read returns."""

    _FT_EVENT_RXCHAR = 1
    _FT_PURGE_RX = 1
    _FT_PURGE_TX = 2
    _WORD_LENGTH = {7: 7, 8: 8}
    _STOP_BITS = {1: 0, 1.5: 1, 2: 2}
    _PARITY = {'N': 0, 'O': 1, 'E': 2, 'M': 3, 'S': 4}
    _FLOW_RTSCTS = 0x100
    _FLOW_DSRDTR = 0x200
    _FLOW_XONXOFF = 0x400
    _XON = 0x11
    _XOFF = 0x13

    _FT_STATUS = {
        0: "FT_OK",
        1: "FT_INVALID_HANDLE",
        2: "FT_DEVICE_NOT_FOUND",
        3: "FT_DEVICE_NOT_OPENED",
        4: "FT_IO_ERROR",
        5: "FT_INSUFFICIENT_RESOURCES",
        6: "FT_INVALID_PARAMETER",
        7: "FT_INVALID_BAUD_RATE",
        8: "FT_DEVICE_NOT_OPENED_FOR_ERASE",
        9: "FT_DEVICE_NOT_OPENED_FOR_WRITE",
        10: "FT_FAILED_TO_WRITE_DEVICE",
        11: "FT_EEPROM_READ_FAILED",
        12: "FT_EEPROM_WRITE_FAILED",
        13: "FT_EEPROM_ERASE_FAILED",
        14: "FT_EEPROM_NOT_PRESENT",
        15: "FT_EEPROM_NOT_PROGRAMMED",
        16: "FT_INVALID_ARGS",
        17: "FT_NOT_SUPPORTED",
        18: "FT_OTHER_ERROR",
    }

    def __init__(
        self,
        port,
        baudrate=9600,
        bytesize=8,
        parity='N',
        stopbits=1,
        timeout=None,
        xonxoff=False,
        rtscts=False,
        write_timeout=None,
        dsrdtr=False,
        exclusive=None,
    ):
        self.port = port
        self._timeout = timeout
        self._baudrate = baudrate
        self._break_condition = False
        self._handle = None

        vid, pid, _ = _get_usb_info(port)
        handle, _, _ = _d2xx_open(port, vid, pid)
        if handle is None:
            raise serial.SerialException(f"{port}: the port is in use")
        self._handle = handle
        self._rx_event = _kernel32.CreateEventW(None, False, False, None)
        self._cancel_event = _kernel32.CreateEventW(None, False, False, None)
        if not (self._rx_event and self._cancel_event):
            _ftd2xx.FT_Close(handle)
            raise ctypes.WinError(ctypes.get_last_error())
        self._finalizer = weakref.finalize(
            self, self._close, handle, self._rx_event, self._cancel_event
        )
        try:
            self._set_baudrate(baudrate)
            self._checkrc(
                _ftd2xx.FT_SetDataCharacteristics,
                handle,
                self._WORD_LENGTH[bytesize],
                self._STOP_BITS[stopbits],
                self._PARITY[parity],
            )
            if sum([xonxoff, rtscts, dsrdtr]) > 1:
                raise ValueError("Only one of xonxoff, rtscts, dsrdtr can be True")
            if rtscts:
                flow = self._FLOW_RTSCTS
            elif dsrdtr:
                flow = self._FLOW_DSRDTR
            elif xonxoff:
                flow = self._FLOW_XONXOFF
            else:
                flow = 0
            self._checkrc(_ftd2xx.FT_SetFlowControl, handle, flow, self._XON, self._XOFF)
            # Reads are only of bytes already received, so the read timeout is not used.
            self._checkrc(
                _ftd2xx.FT_SetTimeouts,
                handle,
                0,
                int(write_timeout * 1000) if write_timeout is not None else 0,
            )
            self._checkrc(_ftd2xx.FT_SetLatencyTimer, handle, 1)
            self._checkrc(
                _ftd2xx.FT_SetEventNotification,
                handle,
                self._FT_EVENT_RXCHAR,
                ctypes.c_void_p(self._rx_event),
            )
            # Discard bytes received before the port was opened, as pyserial does:
            self._checkrc(_ftd2xx.FT_Purge, handle, self._FT_PURGE_RX | self._FT_PURGE_TX)
        except:
            self.close()
            raise

    @staticmethod
    def _close(handle, *events):
        _ftd2xx.FT_Close(handle)
        for event in events:
            _kernel32.CloseHandle(event)

    def _raise_err(self, func, rc):
        msg = f"{func.__name__} error: {self._FT_STATUS.get(rc, f'unknown ({rc})')}"
        raise serial.SerialException(f"{self.port}: {msg}")

    def _checkrc(self, func, *args):
        rc = func(*args)
        if rc != 0:
            self._raise_err(func, rc)

    def write(self, data):
        written = ctypes.c_ulong()
        self._checkrc(
            _ftd2xx.FT_Write,
            self._handle,
            bytes(data),
            len(data),
            ctypes.byref(written),
        )
        return written.value

    def _read_received(self, n):
        buf = ctypes.create_string_buffer(n)
        read_n = ctypes.c_ulong()
        self._checkrc(_ftd2xx.FT_Read, self._handle, buf, n, ctypes.byref(read_n))
        return buf.raw[: read_n.value]

    def _take_cancel(self):
        """Whether `cancel_read` has been called since the last read that it ended.
        Resets it."""
        return _kernel32.WaitForSingleObject(self._cancel_event, 0) == _WAIT_OBJECT_0

    def _wait(self, timeout):
        """Wait until data may have been received, `cancel_read` is called, or `timeout`
        seconds pass (forever if None). Returns whether `cancel_read` was called."""
        events = (wintypes.HANDLE * 2)(self._rx_event, self._cancel_event)
        ms = _INFINITE if timeout is None else int(timeout * 1000 + 1)
        rc = _kernel32.WaitForMultipleObjects(2, events, False, ms)
        return rc == _WAIT_OBJECT_0 + 1

    def read(self, n=1, timeout=_UNSET):
        if timeout is _UNSET:
            timeout = self._timeout
        if timeout is not None:
            deadline = time.perf_counter() + timeout
        chunks = []
        nread = 0
        while nread < n:
            if self._take_cancel():
                break
            available = self.in_waiting
            if available:
                chunk = self._read_received(min(available, n - nread))
                chunks.append(chunk)
                nread += len(chunk)
                continue
            remaining = None
            if timeout is not None:
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    break
            if self._wait(remaining):
                break
        return b''.join(chunks)

    def cancel_read(self):
        _kernel32.SetEvent(self._cancel_event)

    def _set_baudrate(self, baudrate):
        self._checkrc(_ftd2xx.FT_SetBaudRate, self._handle, baudrate)

    @property
    def is_open(self):
        return self._handle is not None

    @property
    def baudrate(self):
        return self._baudrate

    @baudrate.setter
    def baudrate(self, baudrate):
        self._set_baudrate(baudrate)
        self._baudrate = baudrate

    @property
    def break_condition(self):
        return self._break_condition

    @break_condition.setter
    def break_condition(self, value):
        if value:
            self._checkrc(_ftd2xx.FT_SetBreakOn, self._handle)
        else:
            self._checkrc(_ftd2xx.FT_SetBreakOff, self._handle)
        self._break_condition = bool(value)

    @property
    def in_waiting(self):
        n = ctypes.c_ulong()
        self._checkrc(_ftd2xx.FT_GetQueueStatus, self._handle, ctypes.byref(n))
        return n.value

    def close(self):
        if self._handle is not None:
            self._finalizer()
            self._handle = None


class _Serial(_BreakMixin, serial.Serial):
    """``serial.Serial`` with read timeouts implemented in software, and `cancel_read`
    for every platform. The port has a fixed read timeout of 10 ms, since on Windows
    changing the timeouts of an FTDI adaptor after opening the port corrupts data, see
    https://github.com/pyserial/pyserial/issues/394. A read timeout can be passed when
    the port is created. Do not set the `timeout` attribute afterwards; pass a `timeout`
    argument to `read` instead."""

    _MIN_NONZERO_TIMEOUT = 0.010

    def __init__(
        self,
        port,
        baudrate=9600,
        bytesize=8,
        parity='N',
        stopbits=1,
        timeout=None,
        xonxoff=False,
        rtscts=False,
        write_timeout=None,
        dsrdtr=False,
        exclusive=None,
    ):
        self._read_timeout = timeout
        self._cancelled = threading.Event()
        super().__init__(
            port,
            baudrate=baudrate,
            bytesize=bytesize,
            parity=parity,
            stopbits=stopbits,
            timeout=self._MIN_NONZERO_TIMEOUT,
            xonxoff=xonxoff,
            rtscts=rtscts,
            write_timeout=write_timeout,
            dsrdtr=dsrdtr,
            exclusive=exclusive,
        )

    def read(self, n=1, timeout=_UNSET):
        if timeout is _UNSET:
            timeout = self._read_timeout
        if timeout == 0:
            return super().read(min(n, self.in_waiting))
        if timeout is not None:
            deadline = time.perf_counter() + timeout
        chunks = []
        nread = 0
        while nread < n:
            if self._cancelled.is_set():
                self._cancelled.clear()
                break
            chunk = super().read(n - nread)
            chunks.append(chunk)
            nread += len(chunk)
            if timeout is not None and time.perf_counter() > deadline:
                break
        return b''.join(chunks)

    def cancel_read(self):
        self._cancelled.set()


def Serial(
    port,
    baudrate=9600,
    bytesize=8,
    parity='N',
    stopbits=1,
    timeout=None,
    xonxoff=False,
    rtscts=False,
    write_timeout=None,
    dsrdtr=False,
    exclusive=None,
):
    """Open a serial port. Takes the same arguments as ``serial.Serial``.

    For an FTDI adaptor on Linux or Windows, the latency timer is set to 1 ms. On Linux
    this uses the low-latency mode of the ``ftdi_sio`` driver; enabling the mode the
    first time that a port is opened takes 255 ms. On Windows the port is opened through
    FTDI's D2XX library if it is installed, and a warning is issued if it is not. The
    library is available from https://ftdichip.com/drivers/d2xx-drivers/. A port opened
    through D2XX is always exclusive, has the methods and attributes of ``serial.Serial``
    that are listed below, and raises ``serial.SerialException``.

    The returned object has ``read(n=1, timeout)``, ``write(data)``, ``in_waiting``,
    ``cancel_read()``, ``send_break(duration=0.25)``, ``close()``, ``is_open``,
    ``port``, ``baudrate`` and ``break_condition``. Read timeouts are implemented in
    software:

    * If `timeout` is None, ``read()`` blocks until `n` bytes are read.
    * If `timeout` is 0, it returns up to `n` bytes that are available immediately.
    * Otherwise it returns up to `n` bytes received within the timeout.

    The timeout passed to ``read()`` replaces the one given here. Do not set the
    ``timeout`` attribute. ``cancel_read()`` makes a ``read()`` in another thread
    return the bytes read so far; if no read is in progress, the next read returns
    immediately. Reads and writes may be made from different threads at the same time.

    A read returns as soon as the requested bytes arrive. Through pyserial, a read waits
    in steps of 10 ms, about 16 ms on Windows, so it may end up to that long after its
    timeout or a call to ``cancel_read()``. Through D2XX, ``cancel_read()`` ends a read
    immediately, and a read may end up to about 16 ms after its timeout.
    """
    usb_info = _get_usb_info(port)
    ftdi = usb_info is not None and usb_info[0] == _FTDI_VENDOR_ID

    cls = _Serial
    if ftdi and _WINDOWS:
        if _ftd2xx is not None:
            cls = _FTD2xxSerial
        else:
            warnings.warn(_FTD2XX_WARNING)

    dev = cls(
        port,
        baudrate=baudrate,
        bytesize=bytesize,
        parity=parity,
        stopbits=stopbits,
        timeout=timeout,
        xonxoff=xonxoff,
        rtscts=rtscts,
        write_timeout=write_timeout,
        dsrdtr=dsrdtr,
        exclusive=exclusive,
    )

    if ftdi and _LINUX:
        _set_low_latency_serial_linux(dev.fd)

    return dev
