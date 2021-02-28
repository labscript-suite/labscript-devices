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
from blacs.tab_base_classes import Worker
import labscript_utils.properties as properties


class PrawnBlasterWorker(Worker):
    def init(self):
        # fmt: off
        global h5py; import labscript_utils.h5_lock, h5py
        global serial; import serial
        global time; import time
        global re; import re
        self.smart_cache = {}
        self.cached_pll_params = {}
        # fmt: on

        self.prawnblaster = serial.Serial(self.com_port, 115200, timeout=1)
        self.check_status()

        # configure number of pseudoclocks
        self.prawnblaster.write(b"setnumpseudoclocks %d\r\n" % self.num_pseudoclocks)
        assert self.prawnblaster.readline().decode() == "ok\r\n"

        # Configure pins
        for i, (out_pin, in_pin) in enumerate(zip(self.out_pins, self.in_pins)):
            self.prawnblaster.write(b"setoutpin %d %d\r\n" % (i, out_pin))
            assert self.prawnblaster.readline().decode() == "ok\r\n"
            self.prawnblaster.write(b"setinpin %d %d\r\n" % (i, in_pin))
            assert self.prawnblaster.readline().decode() == "ok\r\n"

    def check_status(self):
        self.prawnblaster.write(b"status\r\n")
        response = self.prawnblaster.readline().decode()
        match = re.match(r"run-status:(\d) clock-status:(\d)(\r\n)?", response)
        if match:
            return int(match.group(1)), int(match.group(2)), False
        elif response:
            raise Exception(
                f"PrawnBlaster is confused: saying '{response}' instead of 'run-status:<int> clock-status:<int>'"
            )
        else:
            raise Exception(
                f"PrawnBlaster is returning a invalid status '{response}'. Maybe it needs a reboot."
            )

    def program_manual(self, values):
        for channel, value in values.items():
            pin = int(channel.split()[1])
            pseudoclock = self.out_pins.index(pin)
            if value:
                self.prawnblaster.write(b"go high %d\r\n" % pseudoclock)
            else:
                self.prawnblaster.write(b"go low %d\r\n" % pseudoclock)

            assert self.prawnblaster.readline().decode() == "ok\r\n"

        return values

    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):
        if fresh:
            self.smart_cache = {}

        # Get data from HDF5 file
        pulse_programs = []
        with h5py.File(h5file, "r") as hdf5_file:
            group = hdf5_file[f"devices/{device_name}"]
            for i in range(self.num_pseudoclocks):
                pulse_programs.append(group[f"PULSE_PROGRAM_{i}"][:])
                self.smart_cache.setdefault(i, [])
            device_properties = labscript_utils.properties.get(
                hdf5_file, device_name, "device_properties"
            )
            self.is_master_pseudoclock = device_properties["is_master_pseudoclock"]

        # TODO: Configure clock from device properties
        clock_mode = 0
        clock_vcofreq = 0
        clock_plldiv1 = 0
        clock_plldiv2 = 0
        if device_properties["external_clock_pin"] is not None:
            if device_properties["external_clock_pin"] == 20:
                clock_mode = 1
            elif device_properties["external_clock_pin"] == 22:
                clock_mode = 2
            else:
                raise RuntimeError(
                    f"Invalid external clock pin {device_properties['external_clock_pin']}. Pin must be 20, 22 or None."
                )
        clock_frequency = device_properties["clock_frequency"]

        if clock_mode == 0:
            if clock_frequency == 100e6:
                clock_vcofreq = 1200e6
                clock_plldiv1 = 6
                clock_plldiv2 = 2
            elif clock_frequency in self.cached_pll_params:
                pll_params = self.cached_pll_params[clock_frequency]
                clock_vcofreq = pll_params["vcofreq"]
                clock_plldiv1 = pll_params["plldiv1"]
                clock_plldiv2 = pll_params["plldiv2"]
            else:
                self.logger.info("Calculating PLL parameters...")
                osc_freq = 12e6
                # Techniclally FBDIV can be 16-320 (see 2.18.2 in
                # https://datasheets.raspberrypi.org/rp2040/rp2040-datasheet.pdf )
                # however for a 12MHz reference clock, the range is smaller to ensure
                # vcofreq is between 400 and 1600 MHz.
                found = False
                for fbdiv in range(134, 33, -1):
                    vcofreq = osc_freq * fbdiv
                    # PLL1 div should be greater than pll2 div if possible so we start high
                    for pll1 in range(7, 0, -1):
                        for pll2 in range(1, 8):
                            if vco_freq / (pll1 * pll2) == clock_frequency:
                                found = True
                                clock_vcofreq = vcofreq
                                clock_plldiv1 = pll1
                                clock_plldiv2 = pll2
                                pll_params = {}
                                pll_params["vcofreq"] = clock_vcofreq
                                pll_params["plldiv1"] = clock_plldiv1
                                pll_params["plldiv2"] = clock_plldiv2
                                self.cached_pll_params[clock_frequency] = pll_params
                                break
                        if found:
                            break
                    if found:
                        break
                if not found:
                    raise RuntimeError(
                        "Could not determine appropriate clock paramaters"
                    )

        # Now set the clock details
        self.prawnblaster.write(
            b"setclock %d %d %d %d %d\r\n"
            % (clock_mode, clock_frequency, clock_vcofreq, clock_plldiv1, clock_plldiv2)
        )
        response = self.prawnblaster.readline().decode()
        assert response == "ok\r\n", f"PrawnBlaster said '{response}', expected 'ok'"

        # TODO: Save any information we need for wait monitor

        # Program instructions
        for pseudoclock, pulse_program in enumerate(pulse_programs):
            for i, instruction in enumerate(pulse_program):
                if i == len(self.smart_cache[pseudoclock]):
                    # Pad the smart cache out to be as long as the program:
                    self.smart_cache[pseudoclock].append(None)

                # Only program instructions that differ from what's in the smart cache:
                if self.smart_cache[pseudoclock][i] != instruction:
                    self.prawnblaster.write(
                        b"set %d %d %d %d\r\n"
                        % (pseudoclock, i, instruction["period"], instruction["reps"])
                    )
                    response = self.prawnblaster.readline().decode()
                    assert (
                        response == "ok\r\n"
                    ), f"PrawnBlaster said '{response}', expected 'ok'"
                    self.smart_cache[pseudoclock][i] = instruction

        # All outputs end on 0
        final = {}
        for pin in self.out_pins:
            final[f"GPIO {pin:02d}"] = 0
        return final

    def start_run(self):
        # Start in software:
        self.logger.info("sending start")
        self.prawnblaster.write(b"start\r\n")
        response = self.prawnblaster.readline().decode()
        assert response == "ok\r\n", f"PrawnBlaster said '{response}', expected 'ok'"

    def transition_to_manual(self):
        # TODO: write this
        return True

    def shutdown(self):
        self.prawnblaster.close()

    def abort_buffered(self):
        self.prawnblaster.write(b"abort\r\n")
        assert self.prawnblaster.readline().decode() == "ok\r\n"
        # loop until abort complete
        while self.check_status()[0] != 5:
            time.sleep(0.5)
        return True

    def abort_transition_to_buffered(self):
        return self.abort_buffered()
