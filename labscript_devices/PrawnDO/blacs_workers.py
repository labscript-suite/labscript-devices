#####################################################################
#                                                                   #
# /labscript_devices/PrawnDO/blacs_workers.py                       #
#                                                                   #
# Copyright 2023, Philip Starkey, Carter Turnbaugh, Patrick Miller  #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from blacs.tab_base_classes import Worker
import labscript_utils.h5_lock, h5py
import labscript_utils
from labscript import LabscriptError
import numpy as np
import re
import time

class PrawnDOInterface(object):

    min_version = (1, 2, 0)
    """Minimum compatible firmware version tuple"""

    def __init__(self, com_port, pico_board):
        global serial; import serial
        global struct; import struct

        self.timeout = 0.2
        self.conn = serial.Serial(com_port, 10000000, timeout=self.timeout)
        self.pico_board = pico_board
        
        version = self.get_version()
        print(f'Connected to version: {version}')

        # ensure firmware is compatible
        assert version >= self.min_version, f'Incompatible firmware, must be >= {self.min_version}'
        
        if version >= (1, 3, 0):
            board = self.get_board()
            print(f'Connected to board: {board}')
            print(board, self.pico_board)
            assert board.strip() == self.pico_board.strip(), f'firmware thinks {board} attached, labscript thinks {self.pico_board}'
        else:
            board = 'pico1'
            print(f'Version {version} too low to use pico2 firmware, consider upgrading firmware')
        
        current_status = self.status()
        print(f'Current status is {current_status}')

    def get_version(self):
        '''Sends 'ver' command, which retrieves the Pico firmware version.

        Returns: (int, int, int): Tuple representing semantic version number.'''

        version_str = self.send_command('ver')
        assert version_str.startswith("Version: ")
        version = tuple(int(i) for i in version_str[9:].split('.'))
        assert len(version) == 3

        return version
    
    def get_board(self):
        '''Responds with pico board version.

        Returns:
            (str): Either "pico1" for a Pi Pico 1 board or "pico2" for a Pi Pico 2 board.'''
        resp = self.send_command('brd')
        assert resp.startswith('board:'), f'Board command failed, got: {resp}'
        pico_str = resp.split(':')[-1].strip()

        return pico_str

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
            str: String response from the PrawnDO
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
    
    def status(self):
        '''Reads the status of the PrawnDO
        
        Returns:
            (int, int): tuple containing

                - **run-status** (int): Run status code
                - **clock-status** (int): Clock status code
        
        Raises:
            LabscriptError: If response is not `ok\\r\\n`
        '''
        resp = self.send_command('sts')
        match = re.match(r"run-status:(\d) clock-status:(\d)(\r\n)?", resp)
        if match:
            return int(match.group(1)), int(match.group(2))
        else:
            resp += self._read_full_buffer()
            raise LabscriptError(f'PrawnDO invalid status, returned {repr(resp)}')
        
    def output_state(self):
        '''Reads the current output state of the PrawnDO
        
        Returns:
            int: Output state of all 16 bits
        
        Raises:
            LabscriptError: If response is not `ok\\r\\n`
        '''

        resp = self.send_command('gto')

        try:
            resp_i = int(resp, 16)
        except Exception as e:
            resp += self._read_full_buffer()
            raise LabscriptError(f'Remote value check failed. Got response {repr(resp)}') from e

        return resp_i

    def adm_batch(self, pulse_program):
        '''Sends pulse program as single binary block using `adm` command.
        
        Args:
            pulse_program (numpy.ndarray): Structured array of program to send.
                Must have first column as bit sets (<u2) and second as reps (<u4).
        '''
        self.conn.write('adm 0 {:x}\n'.format(len(pulse_program)).encode())
        resp = self.conn.readline().decode()
        if resp != 'ready\r\n':
            resp += self._read_full_buffer()
            raise LabscriptError(f'adm command failed, got response {repr(resp)}')
        self.conn.write(pulse_program.tobytes())
        resp = self.conn.readline().decode()
        if resp != 'ok\r\n':
            resp += self._read_full_buffer()
            raise LabscriptError(f'Program not written successfully, got response {repr(resp)}')

    def close(self):
        self.conn.close()

class PrawnDOWorker(Worker):
    def init(self):
        self.intf = PrawnDOInterface(self.com_port, self.pico_board)        

        self.smart_cache = {'do_table':None, 'reps':None}

    def _dict_to_int(self, d):
        """Converts dictionary of outputs to an integer mask.
        
        Args:
            d (dict): Dictionary of output states

        Returns:
            int: Integer mask of the 16 output states.
        """
        val = 0
        for conn, value in d.items():
            val |= value << int(conn.split('do')[-1])

        return val
    
    def _int_to_dict(self, val):
        """Converts an integer mask to a dictionary of outputs.
        
        Args:
            val (int): 16-bit integer mask to convert
            
        Returns:
            dict: Dictonary with output channels as keys and values are boolean states
        """
        return {f'do{i:d}':((val >> i) & 1) for i in range(16)}
    
    def check_status(self):
        '''Checks operational status of the PrawnDO.

        Automatically called by BLACS to update status.

        Returns:
            (int, int): Tuple containing:

            - **run-status** (int): Possible values are:

              * 0 : manual mode
              * 1 : transitioning to buffered execution
              * 2 : buffered execution
              * 3 : abort requested
              * 4 : aborting buffered execution
              * 5 : last buffered execution aborted
              * 6 : transitioning to manual mode

            - **clock-status** (int): Possible values are:

              * 0 : internal clock
              * 1 : external clock
        '''

        return self.intf.status()

    def program_manual(self, front_panel_values):
        """Change output states in manual mode.
        
        Returns:
            dict: Output states after command execution.
        """
        value = self._dict_to_int(front_panel_values)
        # send static state
        self.intf.send_command_ok(f'man {value:04x}')
        # confirm state set correctly
        resp_i = self.intf.output_state()

        return self._int_to_dict(resp_i)
    
    def check_remote_values(self):
        """Checks the remote state of the PrawnDO.
        
        Called automatically by BLACS.
        
        Returns:
            dict: Dictionary of the digital output states.
        """

        resp_i = self.intf.output_state()       

        return self._int_to_dict(resp_i)

    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):

        if fresh:
            self.smart_cache = {'pulse_program':None}

        with h5py.File(h5file, 'r') as hdf5_file:
            group = hdf5_file['devices'][device_name]
            if 'pulse_program' not in group:
                # if no output commanded, return
                return
            self.device_properties = labscript_utils.properties.get(
                hdf5_file, device_name, "device_properties")
            pulse_program = group['pulse_program'][()]

        # configure clock from device properties
        ext = self.device_properties['external_clock']
        freq = self.device_properties['clock_frequency']
        self.intf.send_command_ok(f"clk {ext:d} {freq:.0f}")

        # check if it is more efficient to fully refresh
        if not fresh and self.smart_cache['pulse_program'] is not None:

            # get more convenient handle to smart cache array
            curr_program = self.smart_cache['pulse_program']

            # if arrays aren't of same shape, only compare up to smaller array size
            n_curr = len(curr_program)
            n_new = len(pulse_program)
            if n_curr > n_new:
                # technically don't need to reprogram current elements beyond end of new elements
                new_inst = np.sum(curr_program[:n_new] != pulse_program)
            elif n_curr < n_new:
                n_diff = n_new - n_curr
                val_diffs = np.sum(curr_program != pulse_program[:n_curr])
                new_inst = val_diffs + n_diff
            else:
                new_inst = np.sum(curr_program != pulse_program)

            if new_inst / n_new > 0.1:
                fresh = True

        # if fresh or not smart cache, program full table as a batch
        # this is faster than going line by line
        if fresh or self.smart_cache['pulse_program'] is None:
            self.intf.send_command_ok('cls') # clear old program
            self.intf.adm_batch(pulse_program)
            self.smart_cache['pulse_program'] = pulse_program
        else:
            # only program table lines that have changed
            n_cache = len(self.smart_cache['pulse_program'])
            for i, instr in enumerate(pulse_program):
                if i >= n_cache:
                    print(f'programming step {i}')
                    self.intf.send_command_ok(f'set {i:x} {instr[0]:x} {instr[1]:x}')
                    self.smart_cache['pulse_program'][i] = instr

                elif (self.smart_cache['pulse_program'][i] != instr):

                    print(f'programming step {i}')
                    self.intf.send_command_ok(f'set {i:x} {instr[0]:x} {instr[1]:x}')
                    self.smart_cache['pulse_program'][i] = instr

        final_values = self._int_to_dict(pulse_program[-1][0])

        # start program, waiting for beginning trigger from parent
        self.intf.send_command_ok('run')

        return final_values

    def transition_to_manual(self):
        """Transition to manual mode after buffered execution completion.
        
        Returns:
            bool: `True` if transition to manual is successful.
        """
        i = 0
        while True:
            run_status, _ = self.intf.status()
            i += 1
            if run_status == 0:
                return True
            elif i == 1000:
                # program hasn't ended, probably bad triggering
                # abort and raise an error
                self.abort_buffered()
                raise LabscriptError(f'PrawnDO did not end with status {run_status:d}. Is triggering working?')
            elif run_status in [3,4,5]:
                raise LabscriptError(f'PrawnDO returned status {run_status} in transition to manual')

    def abort_buffered(self):
        """Aborts a currently running buffered execution.
        
        Returns:
            bool: `True` is abort was successful.
        """
        self.intf.send_command_ok('abt')
        # loop until abort complete
        while self.intf.status()[0] != 5:
            time.sleep(0.5)
        return True

    def abort_transition_to_buffered(self):
        """Aborts transition to buffered.
        
        Calls :meth:`abort_buffered`
        """
        return self.abort_buffered()

    def shutdown(self):
        """Closes serial connection to PrawnDO"""
        self.intf.close()
