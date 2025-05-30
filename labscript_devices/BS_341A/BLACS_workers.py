import threading

from blacs.tab_base_classes import Worker
from labscript import LabscriptError
from .logger_config import logger
import time
import h5py
import numpy as np
from labscript_utils import properties
from zprocess import rich_print
from datetime import datetime

class BS_341AWorker(Worker):
    def init(self):
        """Initialises communication with the device. When BLACS (re)starts"""
        self.thread = None
        # self.thread_stop_event = threading.Event()

        self.final_values = {}  # [[channel_nums(ints)],[voltages(floats)]]
        self.verbose = True

        try:
            # Try to establish a serial connection
            from .voltage_source import VoltageSource
            self.voltage_source = VoltageSource(self.port, self.baud_rate)

            # Get device information
            self.device_serial = self.voltage_source.device_serial  # For example, 'HV023'
            self.device_voltage_range = self.voltage_source.device_voltage_range # For example, '50'
            self.device_channels = self.voltage_source.device_channels  # For example, '10'
            self.device_output_type = self.voltage_source.device_output_type  # For example, 'b' (bipolar, unipolar, quadrupole, steerer supply)

            logger.info(
                f"Connected to BS-34-1A on {self.port} with baud rate {self.baud_rate}\n"
                f"Device Serial: {self.device_serial}, Voltage Range: {self.device_voltage_range}, "
                f"Channels: {self.device_channels}, Output Type: {self.device_output_type}"
            )

        except LabscriptError as e:
            raise RuntimeError(f"BS-1-10 identification failed: {e}")
        except Exception as e:
            raise RuntimeError(f"An error occurred during BS_341AWorker initialization: {e}")
        
        
    def shutdown(self):
        # Should be done when Blacs is closed
        self.connection.close()
        
    def program_manual(self, front_panel_values): 
        """Allows for user control of the device via the BLACS_tab, 
        setting outputs to the values set in the BLACS_tab widgets. 
        Runs at the end of the shot."""

        rich_print(f"---------- Manual MODE start: ----------", color=PINK)
        self.front_panel_values = front_panel_values

        if self.verbose is True:
            print("Front panel values (before shot):")
            for ch_name, voltage in front_panel_values.items():
                print(f"  {ch_name}: {voltage:.2f} V")

        # Restore final values from previous shot, if available
        if self.final_values and not getattr(self, 'restored_from_final_values', False):
            for ch_num, value in self.final_values.items():
                front_panel_values[f'channel {int(ch_num)}'] = value
            self.restored_from_final_values = True

        if self.verbose is True:
            print("\nFront panel values (after shot):")
            for ch_num, voltage in self.final_values.items():
                print(f"  {ch_num}: {voltage:.2f} V")

        self.final_values = {}  # Empty after restoring

        return front_panel_values

    def check_remote_values(self): # reads the current settings of the device, updating the BLACS_tab widgets 

        return

    def transition_to_buffered(self, device_name, h5_file, initial_values, fresh): 
        """transitions the device to buffered shot mode, 
        reading the shot h5 file and taking the saved instructions from 
        labscript_device.generate_code and sending the appropriate commands 
        to the hardware. 
        Runs at the start of each shot."""
        rich_print(f"---------- Begin transition to Buffered: ----------", color=BLUE)
        self.restored_from_final_values = False  # Drop flag
        self.initial_values = initial_values  # Store the initial values in case we have to abort and restore them
        self.final_values = {}  # Store the final values to update GUI during transition_to_manual
        self.h5file = h5_file # Store path to h5 to write back from front panel
        self.device_name = device_name

        with h5py.File(h5_file, 'r') as hdf5_file:
            group = hdf5_file['devices'][device_name]
            AO_data = group['AO_buffered'][:]
            # self.device_prop = properties.get(hdf5_file, device_name, 'device_properties')
            # print("======== Device Properties : ", self.device_prop, "=========")

        # prepare events
        events = []
        for row in AO_data:
            t = row['time']
            voltages = {ch: row[ch] for ch in row.dtype.names if ch != 'time'}
            events.append((t, voltages))

        # Create and launch thread
        # self.thread_stop_event.clear()
        self.thread = threading.Thread(target=self._playback_thread, args=(events,))
        self.thread.start()

        rich_print(f"---------- End transition to Buffered: ----------", color=BLUE)
        return
        

    def transition_to_manual(self): 
        """transitions the device from buffered to manual mode to read/save measurements from hardware
        to the shot h5 file as results. 
        Runs at the end of the shot."""
        #Stop the thread
        rich_print(f"---------- Begin transition to Manual: ----------", color=BLUE)
        self.thread.join()
        rich_print(f"---------- End transition to Manual: ----------", color=BLUE)
        return True
    
    def abort_transition_to_buffered(self):
        return self.transition_to_manual()

    def _program_manual(self, front_panel_values):
        """Sends voltage values to the device for all channels using VoltageSource.
        """
        if self.verbose is True:
            print("\nProgramming the device with the following values:")
            logger.info("Programming the device from manual with the following values:")

        for channel_num in range(1, int(self.num_AO) + 1):
            channel_name = f'channel {channel_num}'
            voltage = front_panel_values.get(channel_name, 0.0)
            if self.verbose is True:
                print(f"→ {channel_name}: {voltage:.2f} V")
                # logger.info(f"Setting {channel_name} to {voltage:.2f} V (manual mode)")
            self.voltage_source.set_voltage(channel_num, voltage)

    def _get_channel_num(self, channel):
        """Gets channel number with leading zeros 'XX' from strings like 'AOX' or 'channel X'.
        Args:
            channel (str): The name of the channel, e.g. 'AO0', 'AO12', or 'channel 3'.

        Returns:
            str: Two-digit channel number as string, e.g. '01', '12'."""
        ch_lower = channel.lower()
        if ch_lower.startswith("ao"):
            channel_num = channel[2:]  # 'ao3' -> '3'
        elif ch_lower.startswith("channel"):
            _, channel_num = channel.split()  # 'channel 1' -> '1'
        else:
            raise LabscriptError(f"Unexpected channel name format: '{channel}'")

        channel_int = int(channel_num)
        return f"{channel_int:02d}"

    def send_to_BS(self, kwargs):
        """Sends manual values from the front panel to the BS-1-10 device.
            This function is executed in the worker process. It uses the current
            front panel values to reprogram the device in manual mode by clicking the button 'send to device'.
            Args:
                kwargs (dict): Not used currently.
            """
        self._program_manual(self.front_panel_values)
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self._append_front_panel_values_to_manual(self.front_panel_values, current_time)

    def _append_front_panel_values_to_manual(self, front_panel_values, current_time):
        """
            Append front-panel voltage values to the 'AO_manual' dataset in the HDF5 file.

            This method records the current manual voltage settings (from the front panel)
            along with a timestamp into the 'AO_manual' table inside the device's HDF5 group.
            It assumes that `self.h5file` and `self.device_name` have been set
            (in `transition_to_buffered`). If not, a RuntimeError is raised.

            Parameters
            ----------
            front_panel_values : dict
                Dictionary mapping channel names (e.g., 'channel 1') to voltage values (float).
            current_time : str
                The timestamp (formatted as a string) when the values were recorded

            Raises
            ------
            RuntimeError
                If `self.h5file` is not set (i.e., manual values are being saved before
                the system is in buffered mode).
            """
        # Check if h5file is set (transition_to_buffered must be called first)
        if not hasattr(self, 'h5file') or self.h5file is None:
            raise RuntimeError(
                "Cannot save manual front-panel values: "
                "`self.h5file` is not set. Make sure `transition_to_buffered()` has been called before sending to the device."
            )

        with h5py.File(self.h5file, 'r+') as hdf5_file:
            group = hdf5_file['devices'][self.device_name]
            # print("Keys in group:", list(group.keys()))

            dset = group['AO_manual']
            old_shape = dset.shape[0]
            dtype = dset.dtype
            connections = [name for name in dset.dtype.names if name != 'time'] #'ao1'

            # Create new data row
            new_row = np.zeros((1,), dtype=dtype)
            new_row['time'] = current_time
            for conn in connections:
                channel_name = self._ao_to_channel_name(conn)
                new_row[conn] = front_panel_values.get(channel_name, 0.0)

            # Add new row to table
            dset.resize(old_shape + 1, axis=0)
            dset[old_shape] = new_row[0]

    @staticmethod
    def _ao_to_channel_name(ao_name: str) -> str:
        """ Convert 'ao0' to 'channel 0' """
        try:
            channel_index = int(ao_name.replace('ao', ''))
            return f'channel {channel_index}'
        except ValueError:
            raise ValueError(f"Impossible to convert from '{ao_name}'")

    @staticmethod
    def _channel_name_to_ao(channel_name: str) -> str:
        """ Convert 'channel 1' to 'ao1' """
        try:
            channel_index = int(channel_name.replace('channel ', ''))
            return f'ao{channel_index}'
        except ValueError:
            raise ValueError(f"Impossible to convert from '{channel_name}'")

    def _playback_thread(self, events):
        for t, voltages in events:
            if self.verbose:
                # print(f"stop event flag: {self.thread_stop_event.is_set()}")
                print(f"time: {t} \t voltage: {voltages} \n")
            #if self.thread_stop_event.is_set():
                #break

            time.sleep(t)

            for ch_name, voltage in voltages.items():
                ch_num = self._get_channel_num(ch_name) # 'ao1' --> '01'
                self.voltage_source.set_voltage(ch_num, voltage)
                self.final_values[ch_num] = voltage
                if self.verbose:
                    print(f"[{t:.3f}s] --> Set {ch_num} (#{ch_num}) = {voltage}")

        print(f"[Thread] finished all events !")


# --------------------contants
PINK = 'ff52fa'
BLUE = '#66D9EF'