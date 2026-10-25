#####################################################################
#                                                                   #
# /labscript_devices/NarwhalPulseGenerator/driver.py                #
#                                                                   #
# Copyright 2026, Christopher Billington                            #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
# Parts of this file are derived from the ndpulsegen package,       #
# Copyright (c) 2023 RorySpeirs, which is licensed under the MIT    #
# License. See NARWHAL-DEVICES-MIT-LICENSE.txt in this directory.   #
#                                                                   #
#####################################################################
"""Serial driver of the Narwhal Devices Pulse Generator, for firmware 1.002.

The message formats are those of `ndpulsegen.transcode` in
https://github.com/Narwhal-Devices/narwhaldevs-pulsegen. Each message is an
identifier byte followed by little-endian fields.

The device sends notifications at any time, so a thread reads the port and sorts
the messages that arrive: notifications into `PulseGenerator.notifications`,
replies to requests into queues that the request methods read, and errors into a
queue that `raise_errors` drains.
"""

import queue
import random
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import serial
import serial.tools.list_ports

from .. import usbserial

USB_VID = 0x0403
USB_PID = 0x6010
#: USB product strings of the data channel of the Alchitry Au board, as pyserial
#: and, with the channel letter, D2XX report them.
USB_PRODUCTS = ["Alchitry Au", "Alchitry Au B"]
BAUDRATE = 12_000_000
#: The first firmware version that has the message formats of this module.
MIN_FIRMWARE = (1, 2)
#: The device type in the device information of a pulse generator.
DEVICE_TYPE = 1
#: Duration of one cycle of the device clock, in seconds.
CYCLE = 10e-9

MAX_ADDRESS = 8191
MAX_DURATION = 2**48 - 1
MAX_GOTO_COUNTER = 2**32 - 1
MAX_STATE = 2**24 - 1
MAX_TRIGGER_OUT_LENGTH = 255
MAX_TRIGGER_OUT_DELAY = 2**56 - 1
MAX_POWERLINE_DELAY = 2**22 - 1

RUN_MODES = ["single", "continuous"]
ACCEPT_HARDWARE_TRIGGER = ["never", "always", "single_run", "once"]

#: One row per instruction, with the arguments of
#: `ndpulsegen.transcode.encode_instruction`. Bit n of `state` is the level of
#: channel n.
INSTRUCTION_DTYPE = np.dtype(
    [
        ("address", "<u2"),
        ("state", "<u4"),
        ("duration", "<u8"),
        ("goto_address", "<u2"),
        ("goto_counter", "<u4"),
        ("stop_and_wait", "?"),
        ("trigger_out", "?"),
        ("notify", "?"),
        ("powerline_sync", "?"),
    ]
)

_FLAGS = ["stop_and_wait", "trigger_out", "notify", "powerline_sync"]

# Identifiers of messages to the device.
_ECHO = 150
_INSTRUCTION = 151
_ACTION = 152
_OPTIONS = 154
_STATIC_STATE = 155
_POWERLINE_OPTIONS = 156

# Identifiers of messages from the device, and their lengths including the
# identifier.
_ERROR_REPLY = 100
_ECHO_REPLY = 101
_PRINT_REPLY = 102
_STATE_REPLY = 103
_NOTIFICATION = 104
_POWERLINE_REPLY = 105
_RUN_TIME_REPLY = 106
_LENGTHS = {
    _ERROR_REPLY: 3,
    _ECHO_REPLY: 9,
    _PRINT_REPLY: 9,
    _STATE_REPLY: 18,
    _NOTIFICATION: 11,
    _POWERLINE_REPLY: 8,
    _RUN_TIME_REPLY: 9,
}
_ERROR_SUBSYSTEMS = {
    1: "echo",
    2: "instruction",
    3: "action",
    4: "debug",
    5: "device options",
    6: "static state",
    7: "powerline options",
}


class DeviceError(Exception):
    """The device reported an error, or sent a message that cannot be decoded."""


@dataclass(frozen=True)
class DeviceInfo:
    device_type: int
    hardware_version: int
    #: (major, minor), for example (1, 2) for firmware "1.002".
    firmware_version: tuple[int, int]
    serial_number: int


@dataclass(frozen=True)
class DeviceState:
    #: Bit n is the level of channel n.
    state: int
    final_address: int
    trigger_out_delay: int
    trigger_out_length: int
    current_address: int
    run_mode: str
    accept_hardware_trigger: str
    notify_on_trigger_out: bool
    clock_source: str
    running: bool
    software_run_enable: bool
    hardware_run_enable: bool
    notify_when_finished: bool


@dataclass(frozen=True)
class PowerlineState:
    trigger_on_powerline: bool
    locked: bool
    #: Powerline period and trigger delay, in cycles.
    period: int
    trigger_delay: int


@dataclass(frozen=True)
class Notification:
    #: Run time of the device in cycles when the notification was created.
    run_time: int
    address: int
    #: The instruction at `address` has started.
    instruction: bool
    #: The trigger-out pulse at the start of the run has been emitted.
    trigger_out: bool
    #: The run has finished.
    finished: bool
    #: `time.monotonic()` when the notification was received.
    timestamp: float


def firmware_string(version: tuple[int, int]) -> str:
    """The firmware version as the device documentation writes it, e.g. 1.002."""
    return f"{version[0]}.{version[1]:03d}"


def _check(name: str, value: int, maximum: int, minimum: int = 0) -> int:
    if not isinstance(value, int | np.integer) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer in [{minimum}, {maximum}]")
    return int(value)


def _field(name: str, value: int | None, maximum: int, nbytes: int) -> bytes:
    """A fixed-width field, which is zero if the value is None."""
    if value is None:
        return bytes(nbytes)
    return _check(name, value, maximum).to_bytes(nbytes, "little")


def _flag(value: bool | None, shift: int) -> int:
    """A two-bit field: the value, and an update bit that is set if the value is
    not None."""
    return 0 if value is None else (0b10 | bool(value)) << shift


def _choice(name: str, value: str | None, choices: list[str], shift: int) -> int:
    """A field of two value bits and an update bit."""
    if value is None:
        return 0
    if value not in choices:
        raise ValueError(f"{name} must be one of {choices}, not {value!r}")
    return (0b100 | choices.index(value)) << shift


def encode_instructions(instructions: np.ndarray) -> bytes:
    """Encode an array with `INSTRUCTION_DTYPE` as instruction messages."""
    instructions = np.asarray(instructions, dtype=INSTRUCTION_DTYPE)
    for name, maximum, minimum in [
        ("address", MAX_ADDRESS, 0),
        ("duration", MAX_DURATION, 1),
        ("state", MAX_STATE, 0),
        ("goto_address", MAX_ADDRESS, 0),
        ("goto_counter", MAX_GOTO_COUNTER, 0),
    ]:
        if (instructions[name] < minimum).any() or (instructions[name] > maximum).any():
            raise ValueError(f"{name} must be in [{minimum}, {maximum}]")
    if (instructions["powerline_sync"] & (instructions["address"] == 0)).any():
        raise ValueError("The instruction at address 0 cannot have powerline_sync")
    flags = [instructions[name].astype(np.uint8) for name in _FLAGS]
    tags = flags[0] | flags[1] << 1 | flags[2] << 2 | flags[3] << 3
    data = np.zeros((len(instructions), 19), dtype=np.uint8)
    data[:, 0] = _INSTRUCTION
    for column, name, nbytes in [
        (1, "address", 2),
        (3, "state", 3),
        (6, "duration", 6),
        (12, "goto_address", 2),
        (14, "goto_counter", 4),
    ]:
        value = instructions[name].astype(np.uint64)
        for n in range(nbytes):
            data[:, column + n] = (value >> np.uint64(8 * n)) & np.uint64(0xFF)
    data[:, 18] = tags
    return data.tobytes()


def encode_options(
    *,
    final_address: int | None = None,
    run_mode: str | None = None,
    accept_hardware_trigger: str | None = None,
    trigger_out_length: int | None = None,
    trigger_out_delay: int | None = None,
    notify_on_trigger_out: bool | None = None,
    notify_when_finished: bool | None = None,
    software_run_enable: bool | None = None,
) -> bytes:
    """Encode a device options message. An option that is None is not changed."""
    if run_mode is not None and run_mode not in RUN_MODES:
        raise ValueError(f"run_mode must be one of {RUN_MODES}, not {run_mode!r}")
    tags = (
        _flag(None if run_mode is None else run_mode == "continuous", 0)
        | _choice(
            "accept_hardware_trigger",
            accept_hardware_trigger,
            ACCEPT_HARDWARE_TRIGGER,
            2,
        )
        | _flag(notify_on_trigger_out, 5)
        | (final_address is not None) << 7
        | (trigger_out_delay is not None) << 8
        | (trigger_out_length is not None) << 9
        | _flag(software_run_enable, 10)
        | _flag(notify_when_finished, 12)
    )
    return (
        bytes([_OPTIONS])
        + _field("final_address", final_address, MAX_ADDRESS, 2)
        + _field("trigger_out_delay", trigger_out_delay, MAX_TRIGGER_OUT_DELAY, 7)
        + _field("trigger_out_length", trigger_out_length, MAX_TRIGGER_OUT_LENGTH, 1)
        + tags.to_bytes(2, "little")
    )


def encode_powerline_options(
    *, trigger_on_powerline: bool | None = None, trigger_delay: int | None = None
) -> bytes:
    """Encode a powerline options message. An option that is None is not
    changed."""
    tags = (trigger_delay is not None) | _flag(trigger_on_powerline, 1)
    return (
        bytes([_POWERLINE_OPTIONS])
        + _field("trigger_delay", trigger_delay, MAX_POWERLINE_DELAY, 3)
        + bytes([tags])
    )


def encode_action(
    *,
    trigger: bool = False,
    request_state: bool = False,
    request_powerline_state: bool = False,
    disable_after_current_run: bool = False,
    reset_run: bool = False,
    request_run_time: bool = False,
) -> bytes:
    tags = (
        trigger << 0
        | request_state << 1
        | request_powerline_state << 2
        | disable_after_current_run << 3
        | reset_run << 4
        | request_run_time << 5
    )
    return bytes([_ACTION, tags])


def encode_static_state(state: int) -> bytes:
    return bytes([_STATIC_STATE]) + _field("state", state, MAX_STATE, 3)


def _int(data: bytes) -> int:
    return int.from_bytes(data, "little")


def _decode_state(body: bytes) -> DeviceState:
    tags = _int(body[15:17])
    return DeviceState(
        state=_int(body[0:3]),
        final_address=_int(body[3:5]),
        trigger_out_delay=_int(body[5:12]),
        trigger_out_length=body[12],
        current_address=_int(body[13:15]),
        run_mode=RUN_MODES[tags & 1],
        accept_hardware_trigger=ACCEPT_HARDWARE_TRIGGER[(tags >> 1) & 0b11],
        notify_on_trigger_out=bool((tags >> 3) & 1),
        clock_source="internal" if (tags >> 4) & 1 else "external",
        running=bool((tags >> 5) & 1),
        software_run_enable=bool((tags >> 6) & 1),
        hardware_run_enable=bool((tags >> 7) & 1),
        notify_when_finished=bool((tags >> 8) & 1),
    )


def _decode_powerline_state(body: bytes) -> PowerlineState:
    return PowerlineState(
        trigger_on_powerline=bool(body[0] & 1),
        locked=bool((body[0] >> 1) & 1),
        period=_int(body[1:4]),
        trigger_delay=_int(body[4:7]),
    )


def _decode_notification(body: bytes, timestamp: float) -> Notification:
    tags = body[9]
    return Notification(
        run_time=_int(body[0:7]),
        address=_int(body[7:9]),
        instruction=bool(tags & 1),
        trigger_out=bool((tags >> 1) & 1),
        finished=bool((tags >> 2) & 1),
        timestamp=timestamp,
    )


def _decode_info(body: bytes) -> DeviceInfo:
    firmware = _int(body[3:5])
    return DeviceInfo(
        device_type=body[1],
        hardware_version=body[2],
        firmware_version=(firmware // 1000, firmware % 1000),
        serial_number=_int(body[5:8]),
    )


def _decode_error(body: bytes) -> DeviceError:
    tags = body[0]
    subsystem = _ERROR_SUBSYSTEMS.get(body[1], f"subsystem {body[1]}")
    problems = [
        problem
        for bit, problem in enumerate(
            [
                "received an invalid message identifier",
                "timed out waiting for the rest of a message",
                f"could not forward a message to its {subsystem}",
                "executed an instruction with a duration of zero",
            ]
        )
        if (tags >> bit) & 1
    ]
    return DeviceError(f"The device {', and '.join(problems) or 'reported an error'}")


def drain(messages: queue.SimpleQueue) -> list:
    """Remove and return every message in a queue."""
    result = []
    while True:
        try:
            result.append(messages.get_nowait())
        except queue.Empty:
            return result


def find_ports() -> list[str]:
    """The serial ports of the Alchitry Au boards that pulse generators use, and of
    FTDI bridges of the same model whose USB product string is not known."""
    ports = []
    for port in serial.tools.list_ports.comports():
        if port.vid != USB_VID or port.pid != USB_PID:
            continue
        # The bridge has two channels, and the first is the JTAG interface of the
        # device, which Linux also exposes as a serial port.
        if sys.platform == "linux" and (port.location or "").endswith(".0"):
            continue
        product = usbserial.usb_product(port.device)
        if product is not None and product not in USB_PRODUCTS:
            continue
        ports.append(port.device)
    return sorted(ports)


class PulseGenerator:
    """A connection to a pulse generator over an open serial port.

    `open_port` and `connect` create the port. The constructor reads the device
    information into `info`, and checks the firmware version. The device may be
    sending when the port is opened, so the first message read is the reply to an
    echo request with a random byte, and the bytes before it are discarded.
    """

    def __init__(self, port):
        self._port = port
        self._replies: dict[int, queue.SimpleQueue] = {
            identifier: queue.SimpleQueue()
            for identifier in (
                _ECHO_REPLY,
                _STATE_REPLY,
                _POWERLINE_REPLY,
                _RUN_TIME_REPLY,
            )
        }
        self.notifications: queue.SimpleQueue[Notification] = queue.SimpleQueue()
        self._errors: queue.SimpleQueue[Exception] = queue.SimpleQueue()
        self._echo_byte = random.randrange(256)
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()
        try:
            self.info = self._echo()
            if self.info.firmware_version < MIN_FIRMWARE:
                raise DeviceError(
                    "The pulse generator has firmware "
                    f"{firmware_string(self.info.firmware_version)}, but this "
                    f"driver requires firmware {firmware_string(MIN_FIRMWARE)} or "
                    "later"
                )
        except BaseException:
            self.close()
            raise

    @property
    def port(self) -> str:
        return self._port.port

    def close(self) -> None:
        self._port.cancel_read()
        self._thread.join()
        self._port.close()

    def _sync(self) -> bool:
        """Read up to and including the reply to the echo request that the
        constructor sends: the first echo reply with the constructor's random byte, the
        device type of a pulse generator and a nonzero firmware version. Returns False
        if the read was cancelled first."""
        window = bytearray()
        while byte := self._port.read(1):
            window += byte
            if len(window) < _LENGTHS[_ECHO_REPLY]:
                continue
            body = bytes(window[1:])
            if (
                window[0] == _ECHO_REPLY
                and body[0] == self._echo_byte
                and body[1] == DEVICE_TYPE
                and _int(body[3:5]) != 0
            ):
                self._replies[_ECHO_REPLY].put(body)
                return True
            del window[0]
        return False

    def _read(self) -> None:
        try:
            if not self._sync():
                return
            while head := self._port.read(1):
                identifier = head[0]
                if identifier not in _LENGTHS:
                    self._errors.put(
                        DeviceError(
                            f"Received an unknown message identifier {identifier}"
                        )
                    )
                    continue
                body = self._port.read(_LENGTHS[identifier] - 1)
                timestamp = time.monotonic()
                if len(body) < _LENGTHS[identifier] - 1:
                    return
                if identifier == _NOTIFICATION:
                    self.notifications.put(_decode_notification(body, timestamp))
                elif identifier == _ERROR_REPLY:
                    self._errors.put(_decode_error(body))
                elif identifier in self._replies:
                    self._replies[identifier].put(body)
        except serial.SerialException as e:
            self._errors.put(e)

    def raise_errors(self) -> None:
        """Raise the first error that the device reported since the last call."""
        errors = drain(self._errors)
        if errors:
            raise errors[0]

    def _send(self, data: bytes) -> None:
        self._port.write(data)

    def _request(self, data: bytes, reply: int, timeout: float = 1.0) -> bytes:
        replies = self._replies[reply]
        drain(replies)
        self._send(data)
        try:
            return replies.get(timeout=timeout)
        except queue.Empty:
            self.raise_errors()
            raise TimeoutError(
                f"The pulse generator on {self.port} did not reply within {timeout} s"
            ) from None

    def _echo(self) -> DeviceInfo:
        body = self._request(bytes([_ECHO, self._echo_byte]), _ECHO_REPLY)
        return _decode_info(body)

    def write_instructions(self, instructions: np.ndarray) -> None:
        """Load instructions, an array with `INSTRUCTION_DTYPE`, into the device's
        memory."""
        self._send(encode_instructions(instructions))

    def set_options(self, **options: Any) -> None:
        """Set device options. See `encode_options`."""
        self._send(encode_options(**options))

    def set_powerline_options(self, **options: Any) -> None:
        """Set powerline options. See `encode_powerline_options`."""
        self._send(encode_powerline_options(**options))

    def set_static_state(self, state: int) -> None:
        """Set the level of every channel now. Bit n is channel n."""
        self._send(encode_static_state(state))

    def trigger(self) -> None:
        """Send a software trigger, which starts or resumes a run."""
        self._send(encode_action(trigger=True))

    def reset_run(self) -> None:
        """Pause the run and reset the device's progress through its instructions.
        The channels keep their levels. The instructions must be loaded again
        before the next run."""
        self._send(encode_action(reset_run=True))

    def disable_after_current_run(self) -> None:
        self._send(encode_action(disable_after_current_run=True))

    def get_state(self) -> DeviceState:
        body = self._request(encode_action(request_state=True), _STATE_REPLY)
        return _decode_state(body)

    def get_powerline_state(self) -> PowerlineState:
        body = self._request(
            encode_action(request_powerline_state=True), _POWERLINE_REPLY
        )
        return _decode_powerline_state(body)

    def get_run_time(self) -> int:
        """The run time of the device in cycles."""
        body = self._request(encode_action(request_run_time=True), _RUN_TIME_REPLY)
        return _int(body[0:7])


def open_port(port: str) -> PulseGenerator:
    """Open the pulse generator on a serial port."""
    return PulseGenerator(
        usbserial.Serial(
            port, BAUDRATE, timeout=None, write_timeout=1.0, exclusive=True
        )
    )


def connect(serial_number: int | None = None, timeout: float = 5.0) -> PulseGenerator:
    """Open the pulse generator with `serial_number`, or the only one that is
    connected if `serial_number` is None.

    A port that another process holds open, for example a process that is also
    looking for its device, is tried again until `timeout` seconds have passed.
    """
    deadline = time.monotonic() + timeout
    while True:
        found: dict[str, int] = {}
        busy = []
        for port in find_ports():
            try:
                device = open_port(port)
            except serial.SerialException:
                busy.append(port)
                continue
            except (TimeoutError, DeviceError):
                continue
            if device.info.serial_number == serial_number:
                return device
            found[port] = device.info.serial_number
            device.close()
        if serial_number is None and len(found) == 1 and not busy:
            return open_port(next(iter(found)))
        if not busy or time.monotonic() > deadline:
            break
        time.sleep(0.2)
    details = [f"{port}: serial number {number}" for port, number in found.items()]
    details += [f"{port}: in use by another process" for port in busy]
    if serial_number is not None:
        reason = f"No pulse generator has serial number {serial_number}"
    elif len(found) > 1:
        reason = (
            "More than one pulse generator is connected, so a serial number is "
            "required"
        )
    elif found:
        reason = (
            "A serial number is required, since a port that may have another pulse "
            "generator is in use"
        )
    elif busy:
        reason = "No pulse generator is free"
    else:
        reason = "No pulse generator is connected"
    raise DeviceError(f"{reason}. Found: {', '.join(details) or 'none'}")
