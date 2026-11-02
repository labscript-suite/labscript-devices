from labscript_devices import register_classes
from labscript import Device, set_passed_properties, IntermediateDevice, AnalogOut, config
from labscript import IntermediateDevice
import h5py
import numpy as np
from labscript_devices.NI_DAQmx.utils import split_conn_DO, split_conn_AO
from .logger_config import logger

class BS_(IntermediateDevice):
    description = 'BS_Series'
    
    @set_passed_properties(
        property_names={
            "connection_table_properties": [
                "static_AO",
                "baud_rate",
                "port",
                "num_AO",
                "AO_ranges",
                "default_voltage_range",
                "supports_custom_voltages_per_channel",
            ],
        }
    )
    def __init__(
            self,
            name,
            port='',
            baud_rate=9600,
            parent_device=None,
            num_AO=0,
            static_AO = None,
            AO_ranges = [],
            default_voltage_range = [],
            supports_custom_voltages_per_channel = False,
            **kwargs
    ):
        """Initialize a generic BS-series analog output device.

        This constructor supports both devices that share a global analog output
        voltage range, and those that allow custom voltage ranges per channel.

        Args:
           name (str): Name to assign to the created labscript device.
           port (str): Serial port used to connect to the device (e.g. COM3, /dev/ttyUSB0)
           baud_rate (int):
           parent_device (clockline): Parent clockline device that will
               clock the outputs of this device
           num_AO (int): Number of analog output channels.
           AO_ranges (list of dict, optional): A list specifying the voltage range for each AO channel,
            used only if `supports_custom_voltages_per_channel` is True.
            Each item should be a dict of the form:
                {
                    "channel": <int>,  # Channel index
                    "voltage_range": [<float>, <float>]  # Min and max voltage
                }
           static_AO (int, optional): Number of static analog output channels.
           default_voltage_range (iterable): A `[Vmin, Vmax]` pair that sets the analog
                output voltage range for all analog outputs.
           supports_custom_voltages_per_channel (bool): Whether this device supports specifying
            individual voltage ranges for each AO channel.
        """
        self.num_AO = num_AO
        if supports_custom_voltages_per_channel:
            if len(AO_ranges) < num_AO:
                raise ValueError(
                    "AO_ranges must contain at least num_AO entries when custom voltage ranges are enabled.")
            else:
                self.AO_ranges = AO_ranges
        else:
            self.default_voltage_range = default_voltage_range

        IntermediateDevice.__init__(self, name, parent_device, **kwargs)
        self.BLACS_connection = '%s,%s' % (port, str(baud_rate))
    
    def add_device(self, device):
        IntermediateDevice.add_device(self, device)

    def generate_code(self, hdf5_file):
        """Convert the list of commands into numpy arrays and save them to the shot file."""
        logger.info("generate_code for BS 34-1A is called")
        IntermediateDevice.generate_code(self, hdf5_file)

        clockline = self.parent_device
        pseudoclock = clockline.parent_device
        times = pseudoclock.times[clockline]

        # create dataset
        analogs = {}
        for child_device in self.child_devices:
            if isinstance(child_device, AnalogOut):
                analogs[child_device.connection] = child_device

        AO_table = self._make_analog_out_table(analogs, times)
        AO_manual_table = self._make_analog_out_table_from_manual(analogs)
        logger.info(f"Times in generate_code AO table: {times}")
        logger.info(f"AO table for HV-Series is: {AO_table}")

        group = self.init_device_group(hdf5_file)
        group.create_dataset("AO_buffered", data=AO_table, compression=config.compression)
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
            dtypes = [('time', np.float64)] + [(c, np.float32) for c in analogs]  # first column = time

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

        dtypes = [('time', str_dtype)] + [(c, np.float32) for c in analogs]

        analog_out_table = np.empty(0, dtype=dtypes)
        return analog_out_table
