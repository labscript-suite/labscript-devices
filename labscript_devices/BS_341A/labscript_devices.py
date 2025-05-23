from labscript_devices import register_classes
from labscript import Device, set_passed_properties, IntermediateDevice, AnalogOut, config
from labscript import IntermediateDevice
import h5py
import numpy as np
from labscript_devices.NI_DAQmx.utils import split_conn_DO, split_conn_AO
from .logger_config import logger

class BS_341A(IntermediateDevice): # no pseudoclock IntermediateDevice --> Device
    description = 'BS_341A'
    
    @set_passed_properties({"connection_table_properties": ["port", "baud_rate", "num_AO"]})
    def __init__(self, name, port='', baud_rate=115200, parent_device=None, connection=None, num_AO=0, **kwargs):
        IntermediateDevice.__init__(self, name, parent_device, **kwargs)
        # self.start_commands = []
        self.BLACS_connection = '%s,%s' % (port, str(baud_rate))
    
    def add_device(self, device):
        Device.add_device(self, device)

    def generate_code(self, hdf5_file):
        """Convert the list of commands into numpy arrays and save them to the shot file."""
        logger.info("generate_code for BS 34-1A is called")
        IntermediateDevice.generate_code(self, hdf5_file)
        group = self.init_device_group(hdf5_file)

        clockline = self.parent_device
        pseudoclock = clockline.parent_device
        times = pseudoclock.times[clockline]

        # create dataset
        analogs = {}
        for child_device in self.child_devices:
            if isinstance(child_device, AnalogOut):
                analogs[child_device.connection] = child_device

        AO_table = self._make_analog_out_table(analogs, times)
        logger.info(f"Times in generate_code AO table: {times}")
        logger.info(f"AO table for BS-34-1A is: {AO_table}")
        AO_manual_table = self._make_analog_out_table_from_manual(analogs)

        group.create_dataset("AO", data=AO_table, compression=config.compression)
        group.create_dataset("AO_manual", shape=AO_manual_table.shape, maxshape=(None,), dtype=AO_manual_table.dtype,
                             compression=config.compression, chunks=True)


    def _make_analog_out_table(self, analogs, times):
            """Create a structured numpy array with first column as 'time', followed by analog channel data.
            Args:
                analogs (dict): Mapping of connection names to AnalogOut devices.
                times (array-like): Array of time points.
            Returns:
                np.ndarray: Structured array with time and analog outputs.
            """
            if not analogs:
                return None

            n_timepoints = len(times)
            connections = sorted(analogs, key=split_conn_AO)  # sorted channel names
            dtypes = [('time', np.float64)] + [(c, np.float32) for c in connections]  # first column = time

            analog_out_table = np.empty(n_timepoints, dtype=dtypes)

            analog_out_table['time'] = times
            for connection, output in analogs.items():
                analog_out_table[connection] = output.raw_output

            return analog_out_table

    def _make_analog_out_table_from_manual(self, analogs):
        """Create a structured empty numpy array with first column as 'time', followed by analog channel data.
        Args:
            times (array-like): Array of timestamps.
            ...
        Returns:
            np.ndarray: Structured empty array with time and analog outputs."""

        str_dtype = h5py.string_dtype(encoding='utf-8', length=19)

        connections = sorted(analogs, key=split_conn_AO)  # sorted channel names
        dtypes = [('time', str_dtype)] + [(c, np.float32) for c in connections]

        analog_out_table = np.empty(0, dtype=dtypes)
        return analog_out_table
