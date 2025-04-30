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

        # self.SI_to_tuning_words = {
        #     'freq' : (2**32 - 1) / self.sys_clk_freq,
        #     'amp' : 1023.0,
        #     'phase' : 360.0 / 16384.0
        #     }
        
        self.tuning_words_to_SI = {
            'freq' : self.sys_clk_freq / (2**32 - 1) * 10.0,
            'amp' : 1/1023.0,
            'phase' : 360 / 16384.0 * 10.0
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
                                            self.pico_board,
                                            self.sweep_mode,
                                            self.ref_clock_external,
                                            self.ref_clock_frequency, 
                                            self.pll_mult
                                            )
        
        self.smart_cache = {'static_data' : None, 'dds_data' : None}

    def program_manual(self, values):
        '''Called when user makes changes to the front panel. Performs updates 
        to freq, amp, phase by calling 
        :meth:`AD9959DDSSweeperInterface.set_output`'''

        for chan in values:
            chan_int = int(chan[8:])
            self.intf.set_output(chan_int, values[chan]['freq'], values[chan]['amp'], values[chan]['phase'])

    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):

        if fresh:
            self.smart_cache = {'static_data' : None, 'dds_data' : None}

        # Store the initial values in case we have to abort and restore them:
        self.initial_values = initial_values
        # Store the final values for use during transition_to_manual:
        self.final_values = initial_values

        dds_data = None
        stat_data = None

        with h5py.File(h5file, 'r') as hdf5_file:
            group = hdf5_file['devices'][device_name]
            if 'dds_data' in group:
                dds_data = group['dds_data'][()]
                dyn_chans = set([int(n[4:]) for n in dds_data.dtype.names if n.startswith('freq')])
            if 'static_data' in group:
                stat_data = group['static_data'][()]
                stat_chans = set([int(n[4:]) for n in stat_data.dtype.names if n.startswith('freq')])

        if stat_data is not None:

            # update static (final) values
            stat_array = stat_data[:][0]
            for chan in sorted(stat_chans):
                freq = stat_array[f'freq{chan}']
                amp = stat_array[f'amp{chan}']
                phase = stat_array[f'phase{chan}']
                self.intf.set_output(chan, freq, amp, phase)
                self.final_values[f'channel {chan}'] = {
                    'freq' : freq * self.intf.tuning_words_to_SI['freq'],
                    'amp' : amp * self.intf.tuning_words_to_SI['amp'],
                    'phase' : phase * self.intf.tuning_words_to_SI['phase']
                }

        if dds_data is not None:
            self.intf.set_channels(len(dyn_chans))
            self.intf.set_batch(dds_data[()])
            self.intf.stop(len(dds_data[()]))

            # update dynamic final values
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
            self.intf.start()

        if dds_data is None and stat_data is None:
            self.logger.debug('No instructions to set')
            return {}
        
        # self.logger.info(self.final_values)
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
                # self.logger.info('Transition to manual successful')
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
            self.logger.info('Tried to abort buffer, waiting another half second for ABORTED STATUS')
            time.sleep(0.5)
        self.logger.info('Successfully aborted buffered execution')
        
        values = self.initial_values # fix, and update smart cache
        return True

    def abort_transition_to_buffered(self):
        '''Aborts transition to buffered.
        
        Calls :meth:`abort_buffered`'''
        return self.abort_buffered()

    def shutdown(self):
        '''Calls :meth:`AD9959DDSSweeperInterface.close` to end serial connection to AD9959'''
        self.intf.close()
