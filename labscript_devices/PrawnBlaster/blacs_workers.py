#####################################################################
#                                                                   #
# /labscript_devices/PrawnBlaster/blacs_worker.py                   #
#                                                                   #
# Copyright 2021, Philip Starkey                                    #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
import time
import labscript_utils.h5_lock
import h5py
import numpy as np
from blacs.tab_base_classes import Worker
from labscript import LabscriptError
from labscript_utils.connections import _ensure_str
import labscript_utils.properties as properties


class PrawnBlasterWorker(Worker):
    """The primary worker for the PrawnBlaster.

    This worker handles configuration and communication
    with the hardware.
    """

    def init(self):
        """Initialises the hardware communication.

        This function is automatically called by BLACS
        and configures hardware communication with the device.
        """

        # fmt: off
        global h5py; import labscript_utils.h5_lock, h5py
        global serial; import serial
        global time; import time
        global re; import re
        global numpy; import numpy
        global struct; import struct
        global zprocess; import zprocess
        self.smart_cache = {}
        self.cached_pll_params = {}
        # fmt: on

        self.all_waits_finished = zprocess.Event("all_waits_finished", type="post")
        self.wait_durations_analysed = zprocess.Event(
            "wait_durations_analysed", type="post"
        )
        self.wait_completed = zprocess.Event("wait_completed", type="post")
        self.current_wait = 0
        self.wait_table = None
        self.measured_waits = None
        self.wait_timeout = None
        self.h5_file = None
        self.started = False

        self.conn = serial.Serial(self.com_port, 115200, timeout=1)
        self.check_status()

        # configure number of pseudoclocks
        self.send_command_ok(f"setnumpseudoclocks {self.num_pseudoclocks}")

        # Configure pins
        for i, (out_pin, in_pin) in enumerate(zip(self.out_pins, self.in_pins)):
            self.send_command_ok(f"setoutpin {i} {out_pin}")
            self.send_command_ok(f"setinpin {i} {in_pin}")

        version, _ = self.get_version()
        print(f'Connected to version: {version}')

        # Check if fast serial is available
        self.fast_serial = version >= (1, 1, 0)
        print(f'Fast serial available: {self.fast_serial}')

        board = self.get_board()
        print(f'Connected to board: {board}')

    def _read_full_buffer(self):
        '''Used to get any extra lines from device after a failed send_command'''

        resp = self.conn.readlines()
        str_resp = ''.join([st.decode() for st in resp])

        return str_resp
    
    def send_command(self, command, readlines=False):
        '''Sends the supplied string command and checks for a response.
        
        Automatically applies the correct termination characters.
        
        Args:
            command (str): Command to send. Termination and encoding is done automatically.
            readlines (bool, optional): Use pyserial's readlines functionality to read multiple
                response lines. Slower as it relies on timeout to terminate reading.

        Returns:
            str: String response from the PrawnBlaster
        '''
        command += '\r\n'
        self.conn.write(command.encode())

        if readlines:
            str_resp = self._read_full_buffer()
        else:
            str_resp = self.conn.readline().decode()

        return str_resp
    
    def send_command_ok(self, command):
        '''Sends the supplied string command and confirms 'ok' response.

        Args:
            command (str): String command to send.

        Raises:
            LabscriptError: If response is not `ok\\r\\n`
        '''

        resp = self.send_command(command)
        if resp != 'ok\r\n':
            # get complete error message
            resp += self._read_full_buffer()
            raise LabscriptError(f"Command '{command:s}' failed. Got response '{repr(resp)}'")
    
    def get_version(self):
        version_str = self.send_command('version', readlines=True)
        assert version_str.startswith("version: ")
        version = version_str[9:].strip()

        version_overclock_list = version.split('-')
        overclock = False
        if len(version_overclock_list) == 2:
            if version_overclock_list[1] == 'overclock':
                overclock = True

        version = tuple(int(v) for v in version_overclock_list[0].split('.'))
        assert len(version) == 3

        return version, overclock
    
    def get_board(self):
        '''Responds with pico board version.

        Returns:
            (str): Either "pico1" for a Pi Pico 1 board or "pico2" for a Pi Pico 2 board.'''
        resp = self.send_command('board')
        assert resp.startswith('board:'), f'Board command failed, got: {resp}'
        pico_str = resp.split(':')[-1].strip()

        return pico_str

    def check_status(self):
        """Checks the operational status of the PrawnBlaster.

        This is automatically called by BLACS to update the status
        of the PrawnBlaster. It also reads the lengths of any 
        accumulated waits during a shot.

        Returns:
            (int, int, bool): Tuple containing:

            - **run_status** (int): Possible values are: 

                * 0 : manual-mode
                * 1 : transitioning to buffered execution
                * 2 : buffered execution
                * 3 : abort requested
                * 4 : currently aborting buffered execution
                * 5 : last buffered execution aborted
                * 6 : transitioning to manual mode

            - **clock_status** (int): Possible values are:

                * 0 : internal clock
                * 1 : external clock

            - **waits_pending** (bool): Indicates if all expected waits have
              not been read out yet.
        """

        if (
            self.started
            and self.wait_table is not None
            and self.current_wait < len(self.wait_table)
        ):
            # Try to read out wait. For now, we're only reading out waits from
            # pseudoclock 0 since they should all be the same (requirement imposed by labscript)
            response = self.send_command(f'getwait {0}, {self.current_wait}')
            if response != "wait not yet available\r\n":
                # Parse the response from the PrawnBlaster
                wait_remaining = int(response)
                # Divide by two since the clock_resolution is for clock pulses, which
                # have twice the clock_resolution of waits
                # Technically, waits also only have a resolution of `clock_resolution`
                # but the PrawnBlaster firmware accepts them in half of that so that
                # they are easily converted to seconds via the clock frequency.
                # Maybe this was a mistake, but it's done now.
                clock_resolution = self.device_properties["clock_resolution"] / 2
                input_response_time = self.device_properties["input_response_time"]
                timeout_length = round(
                    self.wait_table[self.current_wait]["timeout"] / clock_resolution
                )

                if wait_remaining == (2 ** 32 - 1):
                    # The wait hit the timeout - save the timeout duration as wait length
                    # and flag that this wait timedout
                    self.measured_waits[self.current_wait] = (
                        timeout_length * clock_resolution
                    )
                    self.wait_timeout[self.current_wait] = True
                else:
                    # Calculate wait length
                    # This is a measurement of between the end of the last pulse and the
                    # retrigger signal. We obtain this by subtracting off the time it takes
                    # to detect the pulse in the ASM code once the trigger has hit the input
                    # pin (stored in input_response_time)
                    self.measured_waits[self.current_wait] = (
                        (timeout_length - wait_remaining) * clock_resolution
                    ) - input_response_time
                    self.wait_timeout[self.current_wait] = False

                self.logger.info(
                    f"Wait {self.current_wait} finished. Length={self.measured_waits[self.current_wait]:.9f}s. Timed-out={self.wait_timeout[self.current_wait]}"
                )

                # Inform any interested parties that a wait has completed:
                self.wait_completed.post(
                    self.h5_file,
                    data=_ensure_str(self.wait_table[self.current_wait]["label"]),
                )

                # increment the wait we are looking for!
                self.current_wait += 1

                # post message if all waits are done
                if len(self.wait_table) == self.current_wait:
                    self.logger.info("All waits finished")
                    self.all_waits_finished.post(self.h5_file)

        # Determine if we are still waiting for wait information
        waits_pending = False
        if self.wait_table is not None:
            if self.current_wait == len(self.wait_table):
                waits_pending = False
            else:
                waits_pending = True

        run_status, clock_status = self.read_status()
        return run_status, clock_status, waits_pending

    def read_status(self):
        """Reads the status of the PrawnBlaster.

        Returns:
            (int, int): Tuple containing

                - **run-status** (int): Run status code
                - **clock-status** (int): Clock status code
        """

        response = self.send_command("status", readlines=True)
        match = re.match(r"run-status:(\d) clock-status:(\d)(\r\n)?", response)
        if match:
            return int(match.group(1)), int(match.group(2))
        elif response:
            raise Exception(
                f"PrawnBlaster is confused: saying '{response}' instead of 'run-status:<int> clock-status:<int>'"
            )
        else:
            raise Exception(
                f"PrawnBlaster is returning a invalid status '{response}'. Maybe it needs a reboot."
            )

    def program_manual(self, values):
        """Manually sets the state of output pins for the pseudoclocks.

        Args:
            values (dict): Dictionary of pseudoclock: value pairs to set.

        Returns:
            dict: `values` from arguments on successful programming
            reflecting current output state.
        """

        for channel, value in values.items():
            pin = int(channel.split()[1])
            pseudoclock = self.out_pins.index(pin)
            if value:
                self.send_command_ok(f"go high {pseudoclock}")
            else:
                self.send_command_ok(f"go low {pseudoclock}")

        return values

    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):
        """Configures the PrawnBlaster for buffered execution.

        Args:
            device_name (str): labscript name of PrawnBlaster
            h5file (str): path to shot file to be run
            initial_values (dict): Dictionary of output states at start of shot
            fresh (bool): When `True`, clear the local :py:attr:`smart_cache`, forcing
                a complete reprogramming of the output table.

        Returns:
            dict: Dictionary of the expected final output states.
        """

        if fresh:
            self.smart_cache = {}

        # fmt: off
        self.h5_file = h5file  # store reference to h5 file for wait monitor
        self.current_wait = 0  # reset wait analysis
        self.started = False   # Prevent status check from detecting previous wait values
        #                        betwen now and when we actually send the start signal
        # fmt: on

        # Get data from HDF5 file
        pulse_programs = []
        with h5py.File(h5file, "r") as hdf5_file:
            group = hdf5_file[f"devices/{device_name}"]
            for i in range(self.num_pseudoclocks):
                pulse_programs.append(group[f"PULSE_PROGRAM_{i}"][:])
                self.smart_cache.setdefault(i, [])
            self.device_properties = labscript_utils.properties.get(
                hdf5_file, device_name, "device_properties"
            )
            self.is_master_pseudoclock = self.device_properties["is_master_pseudoclock"]

            # waits
            dataset = hdf5_file["waits"]
            acquisition_device = dataset.attrs["wait_monitor_acquisition_device"]
            timeout_device = dataset.attrs["wait_monitor_timeout_device"]
            if (
                len(dataset) > 0
                and acquisition_device
                == "%s_internal_wait_monitor_outputs" % device_name
                and timeout_device == "%s_internal_wait_monitor_outputs" % device_name
            ):
                self.wait_table = dataset[:]
                self.measured_waits = numpy.zeros(len(self.wait_table))
                self.wait_timeout = numpy.zeros(len(self.wait_table), dtype=bool)
            else:
                self.wait_table = (
                    None  # This device doesn't need to worry about looking at waits
                )
                self.measured_waits = None
                self.wait_timeout = None

        # Configure clock from device properties
        clock_mode = 0
        if self.device_properties["external_clock_pin"] is not None:
            if self.device_properties["external_clock_pin"] == 20:
                clock_mode = 1
            elif self.device_properties["external_clock_pin"] == 22:
                clock_mode = 2
            else:
                raise RuntimeError(
                    f"Invalid external clock pin {self.device_properties['external_clock_pin']}. Pin must be 20, 22 or None."
                )
        clock_frequency = self.device_properties["clock_frequency"]

        # Now set the clock details
        response = self.send_command_ok(f"setclock {clock_mode} {clock_frequency}")

        # Program instructions
        for pseudoclock, pulse_program in enumerate(pulse_programs):
            total_inst = len(pulse_program)
            # check if it is more efficient to fully refresh
            if not fresh and self.smart_cache[pseudoclock] is not None and self.fast_serial:
                # get more convenient handles to smart cache arrays
                curr_inst = self.smart_cache[pseudoclock]

                # if arrays aren't of same shape, only compare up to smaller array size
                n_curr = len(curr_inst)
                n_new = len(pulse_program)
                if n_curr > n_new:
                    # technically don't need to reprogram current elements beyond end of new elements
                    new_inst = np.sum(curr_inst[:n_new] != pulse_program)
                elif n_curr < n_new:
                    n_diff = n_new - n_curr
                    val_diffs = np.sum(curr_inst != pulse_program[:n_curr])
                    new_inst = val_diffs + n_diff
                else:
                    new_inst = np.sum(curr_inst != pulse_program)

                if new_inst / total_inst > 0.1:
                    fresh = True

            if (fresh or self.smart_cache[pseudoclock] is None) and self.fast_serial:
                print('binary programming')
                self.conn.write(b"setb %d %d %d\r\n" % (pseudoclock, 0, len(pulse_program)))
                response = self.conn.readline().decode()
                assert (
                    response == "ready\r\n"
                ), f"PrawnBlaster said '{response}', expected 'ready'"
                program_array = np.array([pulse_program['half_period'],
                                          pulse_program['reps']], dtype='<u4').T
                self.conn.write(program_array.tobytes())
                response = self.conn.readline().decode()
                assert (
                    response == "ok\r\n"
                ), f"PrawnBlaster said '{response}', expected 'ok'"
                self.smart_cache[pseudoclock] = pulse_program
            else:
                print('incremental programming')
                for i, instruction in enumerate(pulse_program):
                    if i == len(self.smart_cache[pseudoclock]):
                        # Pad the smart cache out to be as long as the program:
                        self.smart_cache[pseudoclock].append(None)

                    # Only program instructions that differ from what's in the smart cache:
                    if self.smart_cache[pseudoclock][i] != instruction:
                        self.conn.write(
                            b"set %d %d %d %d\r\n"
                            % (
                                pseudoclock,
                                i,
                                instruction["half_period"],
                                instruction["reps"],
                            )
                        )
                        response = self.conn.readline().decode()
                        assert (
                            response == "ok\r\n"
                        ), f"PrawnBlaster said '{response}', expected 'ok'"
                        self.smart_cache[pseudoclock][i] = instruction

        if not self.is_master_pseudoclock:
            # Start the Prawnblaster and have it wait for a hardware trigger
            self.wait_for_trigger()

        # All outputs end on 0
        final = {}
        for pin in self.out_pins:
            final[f"GPIO {pin:02d}"] = 0
        return final

    def start_run(self):
        """When used as the primary pseudoclock, starts execution
        in software time to engage the shot."""

        # Start in software:
        self.logger.info("sending start")
        self.send_command_ok("start")

        # set started = True
        self.started = True

    def wait_for_trigger(self):
        """When used as a secondary pseudoclock, sets the PrawnBlaster
        to wait for an initial hardware trigger to begin execution."""

        # Set to wait for trigger:
        self.logger.info("sending hwstart")
        self.send_command_ok("hwstart")

        running = False
        while not running:
            run_status, clock_status = self.read_status()
            # If we are running, great, the PrawnBlaster is waiting for a trigger
            if run_status == 2:
                running = True
            # if we are not in TRANSITION_TO_RUNNING, then something has gone wrong
            # and we should raise an exception
            elif run_status != 1:
                raise RuntimeError(
                    f"Prawnblaster did not return an expected status. Status was {run_status}"
                )
            time.sleep(0.01)

        # set started = True
        self.started = True

    def transition_to_manual(self):
        """Transition the PrawnBlaster back to manual mode from buffered execution at
        the end of a shot.

        Returns:
            bool: `True` if transition to manual is successful.
        """

        if self.wait_table is not None:
            with h5py.File(self.h5_file, "a") as hdf5_file:
                # Work out how long the waits were, save em, post an event saying so
                dtypes = [
                    ("label", "a256"),
                    ("time", float),
                    ("timeout", float),
                    ("duration", float),
                    ("timed_out", bool),
                ]
                data = numpy.empty(len(self.wait_table), dtype=dtypes)
                data["label"] = self.wait_table["label"]
                data["time"] = self.wait_table["time"]
                data["timeout"] = self.wait_table["timeout"]
                data["duration"] = self.measured_waits
                data["timed_out"] = self.wait_timeout

                self.logger.info(str(data))

                hdf5_file.create_dataset("/data/waits", data=data)

            self.wait_durations_analysed.post(self.h5_file)

        # If PrawnBlaster is master pseudoclock, then it will have it's status checked
        # in the BLACS tab status check before any transition to manual is called.
        # However, if it's not the master pseudoclock, we need to check here instead!
        if not self.is_master_pseudoclock:
            # Wait until shot completes
            while True:
                run_status, clock_status = self.read_status()
                if run_status == 0:
                    break
                if run_status in [3, 4, 5]:
                    raise RuntimeError(
                        f"Prawnblaster status returned run-status={run_status} during transition to manual"
                    )
                time.sleep(0.01)

        return True

    def shutdown(self):
        """Cleanly shuts down the connection to the PrawnBlaster hardware."""

        self.conn.close()

    def abort_buffered(self):
        """Aborts a currently running buffered execution.

        Returns:
            bool: `True` is abort is successful.
        """
        if not self.is_master_pseudoclock:
            # Only need to send abort signal if we have told the PrawnBlaster to wait
            # for a hardware trigger. Otherwise it's just been programmed with
            # instructions and there is nothing we need to do to abort.
            self.conn.write(b"abort\r\n")
            assert self.conn.readline().decode() == "ok\r\n"
            # loop until abort complete
            while self.read_status()[0] != 5:
                time.sleep(0.5)
        return True

    def abort_transition_to_buffered(self):
        """Aborts a transition to buffered.

        Calls :py:meth:`abort_buffered`.
        """

        return self.abort_buffered()
