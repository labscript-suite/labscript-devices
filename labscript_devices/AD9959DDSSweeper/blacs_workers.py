#####################################################################
#                                                                   #
# /labscript_devices/AD9959DDSSweeper/blacs_workers.py              #
#                                                                   #
# Copyright 2025, Carter Turnbaugh                                  #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################

from blacs.tab_base_classes import Worker
import labscript_utils.h5_lock, h5py

class AD9959DDSSweeperInterface(object):
    def __init__(
                self,
                com_port,
                sweep_mode,
                ref_clock_external,
                ref_clock_frequency,
                pll_mult
                ):
        '''Initializes serial communication and performs initial setup.

        Initial setup consists of checking the version, board, and status.
        The DDS Sweeper is then reset, after which the clock, mode, and debug mode are configured.

        Args:
            com_port (str): COM port assigned to the DDS Sweeper by the OS.
                On Windows, takes the form of `COMd` where `d` is an integer.
            sweep_mode (int):
                The DDS Sweeper firmware can set the DDS outputs in either fixed steps or sweeps of the amplitude, frequency, or phase.
                At this time, only steps are supported, so sweep_mode must be 0.
            ref_clock_external (int): Set to 0 to have Pi Pico provide the reference clock to the AD9959 eval board. Set to 1 for another source of reference clock for the AD9959 eval board.
            ref_clock_frequency (float): Frequency of the reference clock. If ref_clock_external is 0, the Pi Pico system clock will be set to this frequency. If the PLL is used, ref_clock_frequency * pll_mult must be between 100 MHz and 500 MHz. If the PLL is not used, ref_clock_frequency must be less than 500 MHz.
            pll_mult: the AD9959 has a PLL to multiply the reference clock frequency. Allowed values are 1 or 4-20.
        '''
        global serial; import serial

        self.timeout = 0.1
        self.conn = serial.Serial(com_port, 10000000, timeout=self.timeout)

        version = self.get_version()
        print(f'Connected to version: {version}')

        board = self.get_board()
        print(f'Connected to board: {board}')

        current_status = self.get_status()
        print(f'Current status is {current_status}')

        self.conn.write(b'reset\n')
        self.assert_OK()
        self.conn.write(b'setclock %d %d %d\n' % (ref_clock_external, ref_clock_frequency, pll_mult))
        self.assert_OK()
        self.conn.write(b'mode %d 0\n' % sweep_mode)
        self.assert_OK()
        self.conn.write(b'debug off\n')
        self.assert_OK()

    def assert_OK(self):
        '''Read a response from the DDS Sweeper, assert that that response is "ok", the standard response to a successful command.'''
        resp = self.conn.readline().decode().strip()
        assert resp == "ok", 'Expected "ok", received "%s"' % resp

    def get_version(self):
        '''Sends 'version' command, which retrieves the Pico firmware version.

        Returns: (int, int, int): Tuple representing semantic version number.'''
        self.conn.write(b'version\n')
        version_str = self.conn.readline().decode()
        version = tuple(int(i) for i in version_str.split('.'))
        assert len(version) == 3

        # may be better logic for semantic versioning w/o version pkg
        assert version[1] >= 4, f'Version {version} too low'
        return version

    def abort(self):
        '''Stops buffered execution immediately.'''
        self.conn.write(b'abort\n')
        self.assert_OK()

    def start(self):
        '''Starts buffered execution.'''
        self.conn.write(b'start\n')
        self.assert_OK()
    
    def get_status(self):
        '''Reads the status of the AD9959 DDS Sweeper.

        Returns:
            (str): Status in string representation. Accepted values are
                   STOPPED: manual mode
                TRANSITION_TO_RUNNING: transitioning to buffered execution
                RUNNING: buffered execution
                ABORTING: aborting buffered execution
                ABORTED: last buffered execution was aborted
                TRANSITION_TO_STOPPED: transitioning to manual mode'''
        self.conn.write(b'status\n')
        status_str = int(self.conn.readline().decode())
        status_map = {
            0: 'STOPPED',
            1: 'TRANSITION_TO_RUNNING',
            2: 'RUNNING',
            3: 'ABORTING',
            4: 'ABORTED',
            5: 'TRANSITION_TO_STOPPED'
        }
        self.conn.write(b'status\n')
        status_str = int(self.conn.readline().decode())
        if status_str in status_map:
            return status_map[status_str]
        else:
            raise LabscriptError(f'Invalid status, returned {status_str}')
        
    def get_board(self):
        '''Responds with pico board version.

        Returns:
            (str): Either "pico1" for a Pi Pico 1 board or "pico2" for a Pi Pico 2 board.'''
        self.conn.write(b'board\n')
        resp = self.conn.readline().decode()
        return(resp)

    def get_freqs(self):
        '''Responds with a dictionary containing
        the current operating frequencies (in kHz) of various clocks.

        Returns:
            (str): Multi-line string containing clock frequencies in kHz.
                Intended to be human readable, potentially difficult to parse automatically.'''
        self.conn.write(b'getfreqs\n')
        freqs = {}
        while True:
            resp = self.conn.readline().decode()
            if resp == "ok":
                break
            resp = resp.split('=')
            freqs[resp[0].strip()] = int(resp[1].strip()[:-3])
        return freqs

    def set_output(self, channel, frequency, amplitude, phase):
        '''Set frequency, amplitude, and phase of a channel.'''
        self.conn.write(b'setfreq %d %f\n' % (channel, frequency))
        self.assert_OK()
        self.conn.write(b'setamp %d %f\n' % (channel, amplitude))
        self.assert_OK()
        self.conn.write(b'setphase %d %f\n' % (channel, phase))
        self.assert_OK()

    def set_channels(self, channels):
        '''Set number of channels to use in buffered sequence.'''
        self.conn.write(b'setchannels %d\n' % channels)
        self.assert_OK()

    def seti(self, channel, addr, frequency, amplitude, phase):
        '''Set frequency, phase, and amplitude of a channel
        for address addr in buffered sequence from integer values.

        Args:
            channel (int): channel to set the instruction for. Zero indexed.
            addr (int): address of the instruction to set. Zero indexed.
            frequency (unsigned 32 bit int):
                frequency to jump to when this instruction runs.
                In DDS units: ref_clock_frequency * pll_mult / 2^32 * frequency.
            amplitude (unsigned 10 bit int):
                amplitude to jump to when this instruction runs.
                In DDS units: amplitude / 1023 fraction of maximum output amplitude.
            phase (unsigned 14 bit int):
                phase to jump to when this instruction runs.
                In DDS units: 360 * phase / 2^14 degrees.'''
        self.conn.write(b'seti %d %d %f %f %f\n' % (channel, addr, frequency, amplitude, phase))
        self.assert_OK()

    def set_batch(self, table):
        '''Set frequency, phase, and amplitude of a channel
        for address addr in buffered sequence.'''
        self.conn.write(b'setb 0 %d\n' % len(table))
        resp = self.conn.readline().decode()
        if not resp.startswith('ready'):
            resp += ''.join([r.decode() for r in self.conn.readlines()])
            raise LabscriptError(f'setb command failed, got response {repr(resp)}')
        ready_for_bytes = int(resp[len('ready for '):-len(' bytes\n')])
        if ready_for_bytes != len(table.tobytes()):
            self.conn.write(b'\0'*ready_for_bytes)
            self.assert_OK()
            raise LabscriptError(f'Device expected {ready_for_bytes}, but we only had {len(table.tobytes())}. Device mode likely incorrect.')
        self.conn.write(table.tobytes())
        self.assert_OK()

    def stop(self, count):
        '''Set the stop instruction for a buffered sequence.

        Args:
            count (int): number of instructions to run in the buffered sequence.'''
        self.conn.write(b'set 4 %d\n' % count)
        self.assert_OK()

    def close(self):
        '''Closes the serial connection.'''
        self.conn.close()

class AD9959DDSSweeperWorker(Worker):
    def init(self):
        self.intf = AD9959DDSSweeperInterface(
                                            self.com_port, 
                                            self.sweep_mode,
                                            self.ref_clock_external,
                                            self.ref_clock_frequency, 
                                            self.pll_mult
                                            )

    def program_manual(self, values):
        self.intf.abort()

        for chan in values:
            chan_int = int(chan[8:])
            self.intf.set_output(chan_int, values[chan]['freq'], values[chan]['amp'], values[chan]['phase'])

    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):
        self.final_values = initial_values

        with h5py.File(h5file, 'r') as hdf5_file:
            group = hdf5_file['devices'][device_name]
            dds_data = group['dds_data']

            if 'static_data' in group:
                stat_data = group['static_data']
                stat_chans = set([int(n[4:]) for n in stat_data.dtype.names if n.startswith('freq')])

            if len(dds_data) == 0:
                # Don't bother transitioning to buffered if no data
                return {}
            
            if len(stat_data) > 0:
                stat_array = stat_data[()]
                for chan in sorted(stat_chans):
                    freq = stat_array[f'freq{chan}']
                    amp = stat_array[f'amp{chan}']
                    phase = stat_array[f'phase{chan}']
                    self.intf.set_output(chan, freq, amp, phase)

            dyn_chans = set([int(n[4:]) for n in dds_data.dtype.names if n.startswith('freq')])
            self.intf.set_channels(len(dyn_chans))
            self.intf.set_batch(dds_data[()])
            self.intf.stop(len(dds_data[()]))

        self.intf.start()

        return {}

    def transition_to_manual(self):
        if self.final_values:
            self.program_manual(self.final_values)
        return True

    def abort_buffered(self):
        return self.transition_to_manual()

    def abort_transition_to_buffered(self):
        return self.transition_to_manual()

    def shutdown(self):
        self.intf.close()
