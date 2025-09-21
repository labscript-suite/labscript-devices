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
import time
import numpy as np
from labscript import LabscriptError

class AD9959DDSSweeperInterface(object):
    def __init__(
                self,
                com_port,
                pico_board,
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
            pico_board (str): The version of pico board used, 'pico1' or 'pico2'.
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

        self.min_ver = (0, 4, 0)
        self.status_map = {
            0: 'STOPPED',
            1: 'TRANSITION_TO_RUNNING',
            2: 'RUNNING',
            3: 'ABORTING',
            4: 'ABORTED',
            5: 'TRANSITION_TO_STOPPED'
        }

        self.sys_clk_freq = ref_clock_frequency * pll_mult
        
        self.tuning_words_to_SI = {
            'freq' : self.sys_clk_freq / (2**32 - 1),
            'amp' : 1/1023.0,
            'phase' : 360 / 16384.0
        }
        
        self.subchnls = ['freq', 'amp', 'phase']

        version = self.get_version()
        print(f'Connected to version: {version}')

        board = self.get_board()
        print(f'Connected to board: {board}')
        assert board.strip() == pico_board.strip(), f'firmware thinks {board} attached, labscript thinks {pico_board}'

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

        assert version >= self.min_ver, f'Version {version} too low'
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
            (str): Status in string representation. Accepted values are:

                STOPPED: manual mode\n
                TRANSITION_TO_RUNNING: transitioning to buffered execution\n
                RUNNING: buffered execution\n
                ABORTING: aborting buffered execution\n
                ABORTED: last buffered execution was aborted\n
                TRANSITION_TO_STOPPED: transitioning to manual mode'''

        self.conn.write(b'status\n')
        status_str = self.conn.readline().decode()
        status_int = int(status_str)
        if status_int in self.status_map:
            return self.status_map[status_int]
        else:
            raise LabscriptError(f'Invalid status, returned {status_str}')
        
    def get_board(self):
        '''Responds with pico board version.

        Returns:
            (str): Either "pico1" for a Pi Pico 1 board or "pico2" for a Pi Pico 2 board.'''
        self.conn.write(b'board\n')
        resp = self.conn.readline().decode()
        return resp

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
        '''Set frequency, phase, and amplitude of a channel
        outside of the buffered sequence from floating point values.

        Args:
            channel (int): channel to set the instruction for. Zero indexed.
            frequency (float):
                frequency of output. Floating point number in Hz (0-DDS clock/2).
                Will be rounded during quantization to DDS units.
            amplitude (float):
                amplitude of output. Fraction of maximum output amplitude (0-1).
                Will be rounded during quantization to DDS units.
            phase (float):
                phase of output. Floating point number in degrees (0-360).
                Will be rounded during quantization to DDS units.'''
        self.conn.write(b'setfreq %d %f\n' % (channel, frequency))
        self.assert_OK()
        self.conn.write(b'setamp %d %f\n' % (channel, amplitude))
        self.assert_OK()
        self.conn.write(b'setphase %d %f\n' % (channel, phase))
        self.assert_OK()

    def set_channels(self, channels):
        '''Set number of channels to use in buffered sequence.

        Args:
            channels (int):
                If 1-4, sets the number of channels activated for buffered mode.
                Lowest channels are always used first.
                If 0, simultaneously updates all channels during buffered mode.'''
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
        cmd = f'seti {channel} {addr} {int(frequency)} {int(amplitude)} {int(phase)}\n'
        self.conn.write(cmd.encode())
        # self.conn.write(b'seti %d %d %f %f %f\n' % (channel, addr, frequency, amplitude, phase))
        self.assert_OK()

    def set_batch(self, table):
        '''Set frequency, phase, and amplitude of all channels
        for many addresses in buffered sequence from integer values in a table.

        Uses binary instruction encoding in transit to improve write speeds.
        :meth:`set_batch` does not send a stop instruction, so call :meth:`stop` separately.

        Args:
            table (numpy array):
                Table should be an array of instructions in a mode-dependent format.
                The dtypes should be repeated for each channel, with channel 0s parameters
                first, followed by channel1s parameters, etc. depending on the number of channels.
                The formats for each channel are as follows:
                Single-step mode: ('frequency', '<u4'), ('amplitude', '<u2'), ('phase', '<u2')
                Amplitude sweep mode: ('start_amplitude', '<u2'), ('stop_amplitude', '<u2'), ('delta', '<u2'), ('rate', '<u1')
                Frequency sweep mode: ('start_frequency', '<u4'), ('stop_frequency', '<u4'), ('delta', '<u4'), ('rate', '<u1')
                Phase sweep mode: ('start_phase', '<u2'), ('stop_phase', '<u2'), ('delta', '<u2'), ('rate', '<u1')
                Amplitude sweep mode with steps: ('start_amplitude', '<u2'), ('stop_amplitude', '<u2'), ('delta', '<u2'), ('rate', '<u1'), ('frequency', '<u4'), ('phase', '<u2')
                Frequency sweep mode with steps: ('start_frequency', '<u4'), ('stop_frequency', '<u4'), ('delta', '<u4'), ('rate', '<u1'), ('amplitude', '<u2'), ('phase', '<u2')
                Phase sweep mode with steps: ('start_phase', '<u2'), ('stop_phase', '<u2'), ('delta', '<u2'), ('rate', '<u1'), ('frequency', '<u4'), ('amplitude', '<u2')
        Raises: LabscriptError if the table is not compatible with the device's current mode.'''
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
                                            self.pico_board,
                                            self.sweep_mode,
                                            self.ref_clock_external,
                                            self.ref_clock_frequency, 
                                            self.pll_mult
                                            )
        
        self.smart_cache = {'static_data' : None, 'dds_data' : None}

    def _update_final_values(self, dds_data, dyn_chans):
        '''Updates the final values in place using the last entry of dynamic 
        data. Only for internal use.'''
        last_entries = dds_data[-1]
        for chan in sorted(dyn_chans):
            freq = last_entries[f'freq{chan}']
            amp = last_entries[f'amp{chan}']
            phase = last_entries[f'phase{chan}']
            self.final_values[f'channel {chan}'] = {
                'freq' : freq * self.intf.tuning_words_to_SI['freq'],
                'amp' : amp * self.intf.tuning_words_to_SI['amp'],
                'phase' : phase * self.intf.tuning_words_to_SI['phase']
            }

    def program_manual(self, values):
        '''Called when user makes changes to the front panel. Performs updates 
        to freq, amp, phase by calling 
        :meth:`AD9959DDSSweeperInterface.set_output`
        
        Args:
            values (dict): dictionary of dictionaries with keys of active DDS 
            channels, subkeys of ['freq', 'amp', 'phase']
        '''
        self.smart_cache['static_data'] = None

        for chan in values:
            chan_int = int(chan[8:])
            self.intf.set_output(chan_int, values[chan]['freq'], values[chan]['amp'], values[chan]['phase'])

    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):
        '''Configure the DDS Sweeper for buffered execution.

        First, data is loaded from the shot files.
        Then, static channels are set using the :meth:`set_output` function.
        Next, dynamic data is loaded.
            If the sequence has run before, the smart cache is used to minimize new updates.
        Finally, buffered execution is started.

        Args:
            device_name (str): labscript name of DDS Sweeper
            h5file (str): path to shot file to run
            initial_values (dict): Dictionary of output states at start of shot
            fresh (bool): When `True`, clear the local :py:attr:`smart_cache`, forcing
                a complete reprogramming of the output table.

        Returns:
            dict: Dictionary of the expected final output states.
        '''
        if fresh:
            self.logger.debug('\n------------Clearing smart cache for fresh start-----------')
            self.smart_cache = {'static_data' : None, 'dds_data' : None}

        # Store the initial values in case we have to abort and restore them:
        self.initial_values = initial_values
        # Store the final values for use during transition_to_manual:
        self.final_values = initial_values

        dds_data = None
        stat_data = None

        # get data to program from shot, if defined
        with h5py.File(h5file, 'r') as hdf5_file:
            group = hdf5_file['devices'][device_name]
            if 'dds_data' in group:
                dds_data = group['dds_data'][()]
                dyn_chans = set([int(n[4:]) for n in dds_data.dtype.names if n.startswith('freq')])
            if 'static_data' in group:
                stat_data = group['static_data'][()]
                stat_chans = set([int(n[4:]) for n in stat_data.dtype.names if n.startswith('freq')])

        # handle static channels
        if stat_data is not None:
            self.logger.debug(f'Static Data found')
            stat_array = stat_data[0]

            if self.smart_cache['static_data'] is None:
                self.smart_cache['static_data'] = np.zeros_like(stat_array)
                
            for chan in sorted(stat_chans):
                freq = stat_array[f'freq{chan}']
                amp = stat_array[f'amp{chan}']
                phase = stat_array[f'phase{chan}']

                cache_freq = self.smart_cache['static_data'][f'freq{chan}']
                cache_amp = self.smart_cache['static_data'][f'amp{chan}']
                cache_phase = self.smart_cache['static_data'][f'phase{chan}']
        
                if fresh or freq != cache_freq or amp != cache_amp or phase != cache_phase:
                    self.logger.debug(f'Setting fresh outputs on chan: {chan}')
                    self.intf.set_output(chan, freq, amp, phase)
                    self.final_values[f'channel {chan}'] = {
                        'freq' : freq,
                        'amp' : amp,
                        'phase' : phase,
                    }
        
        if dds_data is not None:
            self.logger.debug(f'Dynamic Data found')

            # check if it is more efficient to fully refresh
            # using boolean mask of lines that differ here for later 
            # line-by-line programming
            if not fresh and self.smart_cache['dds_data'] is not None:
                self.logger.debug('Checking to see if more efficient to fully refresh')

                cache = self.smart_cache['dds_data']

                #  check where the cache and table are equal
                min_len = min(len(cache), len(dds_data))
                equal_mask = cache[:min_len] == dds_data[:min_len]
                n_diff = np.count_nonzero(~equal_mask)

                # check where they differ
                n_total = max(len(cache), len(dds_data))
                n_extra = abs(len(cache) - len(dds_data))
                changed_ratio = (n_diff + n_extra) / n_total

                # past a 10% change, force a refresh
                if changed_ratio > 0.1:
                    self.logger.debug(f'Changed ratio: {changed_ratio:.2%}, refreshing fully')
                    fresh = True
            
            elif self.smart_cache['dds_data'] is None:
                fresh = True

            # Fresh starts use the faster binary batch mode
            if fresh:
                self.logger.debug('Programming a fresh set of dynamic instructions')
                self.intf.set_channels(len(dyn_chans))
                self.intf.set_batch(dds_data)
                self.intf.stop(len(dds_data))
                self.smart_cache['dds_data'] = dds_data.copy()
                self.logger.debug('Updating dynamic final values via batch')
                self._update_final_values(dds_data, dyn_chans)
                self.intf.start()

            # If only a few changes, incrementally program only the differing
            # instructions
            else:
                self.intf.set_channels(len(dyn_chans))
                self.logger.debug('Comparing changed instructions')
                cache = self.smart_cache['dds_data']
                n_cache = len(cache)

                # Extend cache if necessary
                if len(dds_data) > n_cache:
                    new_cache = np.empty(len(dds_data), dtype=dds_data.dtype)
                    new_cache[:n_cache] = cache
                    self.smart_cache['dds_data'] = new_cache
                    cache = new_cache

                # Boolean mask of each rows
                changed_mask = np.zeros(len(dds_data), dtype=bool)
                for name in dds_data.dtype.names:

                    # need to check field-by-field, both vals and dtypes
                    diffs = np.where(cache[:len(dds_data)][name] != dds_data[name])[0]
                    if diffs.size > 0:
                        self.logger.debug(f"Field {name} differs at rows: {diffs}")
                    field_dtype = dds_data[name].dtype
                    if np.issubdtype(field_dtype, np.floating):
                        changed_mask |= ~np.isclose(cache[:len(dds_data)][name], dds_data[name])
                    else:
                        changed_mask |= cache[:len(dds_data)][name] != dds_data[name]

                changed_indices = np.where(changed_mask)[0]
                # Handle potential row count difference
                if n_cache != len(dds_data):
                    self.logger.debug(f"Length mismatch: cache has {n_cache}, dds_data has {len(dds_data)}")
                    changed_indices = np.union1d(changed_indices, np.arange(len(dds_data), n_cache))
                self.logger.debug(f"Changed rows: {changed_indices}")

                # Iterate only over changed rows
                for i in changed_indices:
                    self.logger.debug(f'Smart cache differs at index {i}')
                    if i >= len(dds_data):
                        self.logger.warning(f"Skipping seti at index {i} — beyond dds_data length")
                        continue
                    for chan in sorted(dyn_chans):
                        freq = dds_data[i][f'freq{chan}']
                        amp = dds_data[i][f'amp{chan}']
                        phase = dds_data[i][f'phase{chan}']
                        self.logger.debug(f'seti {chan} {i} {freq} {amp} {phase}')
                        self.intf.seti(int(chan), int(i), int(freq), int(amp), int(phase))
                    for name in dds_data.dtype.names:
                        cache[i][name] = dds_data[i][name]

                self.smart_cache['dds_data'] = cache[:len(dds_data)]
                self.intf.stop(len(dds_data))
                self.logger.debug('Updating dynamic final values with smart cache')
                self._update_final_values(self.smart_cache['dds_data'], dyn_chans)
                self.intf.start()

        return self.final_values

    def transition_to_manual(self):
        '''Handles period between programmed instructions and return to front 
        panel control. Device will move from RUNNING -> TRANSITION_TO_STOPPED 
        -> STOPPED ideally. If buffered execution takes too long, calls
        :meth:`abort_buffered`'''

        i = 0
        while True:
            status = self.intf.get_status()
            i += 1
            if status == 'STOPPED':
                self.logger.debug('Transition to manual successful')
                return True
            
            elif i == 1000:
                # program hasn't ended, probably bad triggering
                # abort and raise an error
                self.abort_buffered()
                raise LabscriptError(f'Buffered operation did not end with status {status}. Is triggering working?')
            elif status in ['ABORTING', 'ABORTED']:
                raise LabscriptError(f'AD9959 returned status {status} in transition to manual')

    def abort_buffered(self):
        '''Aborts currently running program, ensuring ABORTED status. 
        Additionally updates front panels with values before run start and 
        updates smart cache before return.'''
        self.intf.abort()
        while self.intf.get_status() != 'ABORTED':
            self.logger.debug('Tried to abort buffer, waiting another half second for ABORTED STATUS')
            time.sleep(0.5)
        self.logger.debug('Successfully aborted buffered execution')
        
        # return state to initial values
        values = self.initial_values # fix, and update smart cache
        self.logger.debug(f'Returning to values: {values}')
        self.smart_cache['static_data'] = None
        self.smart_cache['dds_data'] = None
        self.program_manual(values)
        return True

    def abort_transition_to_buffered(self):
        '''Aborts transition to buffered.
        
        Calls :meth:`abort_buffered`'''
        return self.abort_buffered()

    def shutdown(self):
        '''Calls :meth:`AD9959DDSSweeperInterface.close` to end serial connection to AD9959'''
        self.intf.close()
