import serial
import numpy as np
from labscript.labscript import LabscriptError
from .logger_config import logger

class VoltageSource:
    """ Voltage Source for ST BS 34-1/BS 1-8 class to establish and maintain the communication with the connection.
    """
    def __init__(self,
                 port,
                 baud_rate,
                 verbose=False
                 ):
        logger.debug(f"<initialising Voltage Source>")
        self.verbose = verbose
        self.port = port
        self.baud_rate = baud_rate

        # connecting to connectionice
        self.connection = serial.Serial(self.port, self.baud_rate, timeout=1)
        device_info = self.identify_query()
        self.device_serial = device_info[0]  # For example, 'HV023'
        self.device_voltage_range = device_info[1]  # For example, '50'
        self.device_channels = device_info[2]  # For example, '10'
        self.device_output_type = device_info[3]  # For example, 'b' (bipolar, unipolar, quadrupole, steerer supply)

    def identify_query(self):
        """Send identification instruction through serial connection, receive response.
           Returns:
               list[str]: Parsed identity response split by whitespace.
           Raises:
               LabscriptError: If identity format is incorrect.
           """
        self.connection.write("IDN\r".encode())
        raw_response = self.connection.readline().decode()
        identity = raw_response.split()

        if len(identity) == 4:
            logger.debug(f"Device initialized with identity: {identity}")
            return identity
        else:
            raise LabscriptError(
                f"Device identification failed.\n"
                f"Raw identity: {raw_response!r}\n"
                f"Parsed identity: {identity!r}\n"
                f"Expected format: ['BSXXX', 'RRR', 'CC', 'b']\n"
                f"Device: BS-1-10 at port {self.port!r}\n"
            )

    def set_voltage(self, channel_num, value):
        """ Send set voltage command to device.
        Args:
            channel_num (str): Channel number.
            value (float): Voltage value to set.
        Raises:
            LabscriptError: If the response from BS-1-10 is incorrect.
        """
        try:
            channel_num = f"{int(channel_num) + 1}"
            channel = f"CH{int(channel_num):02d}"
            scaled_voltage = self._scale_to_normalized(float(value), float(self.device_voltage_range))
            send_str = f"{self.device_serial} {channel} {scaled_voltage:.5f}\r"

            self.connection.write(send_str.encode())
            response = self.connection.readline().decode().strip() #'CHXX Y.YYYYY'

            logger.debug(f"Sent to BS-34/BS-1-8: {send_str!r} | Received: {response!r}")

            expected_response = f"{channel} {scaled_voltage:.5f}"
            if response != expected_response:
                raise LabscriptError(
                    f"Voltage setting failed.\n"
                    f"Sent command: {send_str.strip()!r}\n"
                    f"Expected response: {expected_response!r}\n"
                    f"Actual response: {response!r}\n"
                    f"Device: BS-1-10 at port {self.port!r}"
                )
        except Exception as e:
            raise LabscriptError(f"Error in set_voltage: {e}")

    def read_temperature(self):
        """
        Query the device for temperature.
        Returns:
            float: Temperature in Celsius.
        Raises:
            LabscriptError: If the response format is invalid or parsing fails.
        """
        send_str = f"{self.device_serial} TEMP\r"
        self.connection.write(send_str.encode())

        response = self.connection.readline().decode().strip() #'TEMP XXX.X°C'

        if response.endswith("°C"):
            try:
                # Remove the degree symbol and parse the number
                _, temperature_str_raw = response.split() # 'TEMP' 'XXX.X°C'
                temperature_str = temperature_str_raw.replace("°C", "").strip()
                temperature = float(temperature_str)
                return temperature
            except ValueError:
                raise LabscriptError(f"Failed to parse temperature from response.\n")
        else:
            raise LabscriptError(
                f"Temperature query failed.\n"
                f"Unexpected response format: {response!r}\n"
                f"Expected a value ending in '°C'."
            )

    def voltage_query(self, channel_num):
        """
        Query voltage on the channel.
        Args:
            channel_num (int): Channel number.
        Returns:
            float: voltage in Volts.
        Raises:
            LabscriptError: If the response format is invalid or parsing fails.
        """

        channel = f"{int(channel_num):02d}" # 1 -> '01'
        send_str = f"{self.device_serial} U{channel}\r" # 'DDDDD UXX'
        self.connection.write(send_str.encode())

        response = self.connection.readline().decode().strip()  # '+/-yy,yyy V'

        if response.endswith("V"):
            try:
                numeric_part = response[:-1].strip()  # remove 'V' and whitespace
                numeric_part = numeric_part.replace(',', '.')  # convert to Python-style float
                voltage = float(numeric_part)
                return voltage
            except ValueError:
                raise LabscriptError(f"Failed to parse voltage from response.\n")
        else:
            raise LabscriptError(
                f"Voltage query failed.\n"
                f"Unexpected response format: {response!r}\n"
                f"Expected a value ending in 'V'."
            )

    def current_query(self, channel_num):
        """
        Query current on the channel.
        Args:
            channel_num (int): Channel number.
        Returns:
            float: current in milliAmpere
        Raises:
            LabscriptError: If the response format is invalid or parsing fails.
        """

        channel = f"{int(channel_num):02d}" # 1 -> '01'
        send_str = f"{self.device_serial} I{channel}\r" # 'DDDDD IXX' #TODO: is it I or l or 1?
        self.connection.write(send_str.encode())

        response = self.connection.readline().decode().strip()  # '+/-yy,yyy mA'

        if response.endswith("mA"):
            try:
                numeric_part = response[:-1].strip()  # remove 'mA' and whitespace
                numeric_part = numeric_part.replace(',', '.')  # convert to Python-style float
                current = float(numeric_part)
                return current
            except ValueError:
                raise LabscriptError(f"Failed to parse current from response.\n")
        else:
            raise LabscriptError(
                f"Current query failed.\n"
                f"Unexpected response format: {response!r}\n"
                f"Expected a value ending in 'mA'."
            )

    def vol_curr_query(self, channel_num):
        """
       Query voltage and current on the channel.
       Args:
           channel_num (int): Channel number.
       Returns:
           float: voltage in Volts.
           float: cuurent in milliAmpere
       Raises:
           LabscriptError: If the response format is invalid or parsing fails.
       """
        channel = f"{int(channel_num):02d}"  # 1 -> '01'
        send_str = f"{self.device_serial} Q{channel}\r"  # 'DDDDD QXX'
        self.connection.write(send_str.encode())

        response = self.connection.readline().decode().strip()  # '+/-yy,yyy V +/-z,zzz mA'

        if response.endswith("mA"):
            try:
                parts = response.split("V")
                numeric_vol = parts[0].strip()  # e.g., '+12,345'
                numeric_curr = parts[1].replace("mA", "").strip()  # e.g., '-00,123'
                numeric_vol = numeric_vol.replace(',', '.')  # convert to Python-style float
                numeric_curr = numeric_curr.replace(',', '.')
                voltage = float(numeric_vol)
                current = float(numeric_curr)
                return voltage, current

            except (ValueError, IndexError) as e:
                raise LabscriptError(
                    f"Failed to parse voltage and current from response: {response!r}"
                ) from e
        else:
            raise LabscriptError(
                f"Voltage and Current query failed.\n"
                f"Unexpected response format: {response!r}\n"
                f"Expected format like '+12,345 V -00,123 mA'."
            )

    def _scale_to_range(self, normalized_value, max_range):
        """Convert a normalized value (0 to 1) to the specified range (-max_range to +max_range)"""
        max_range = float(max_range)
        return 2 * max_range * normalized_value - max_range

    def _scale_to_normalized(self, actual_value, max_range):
        """Convert an actual value (within -max_range to +max_range) to a normalized value (0 to 1)"""
        max_range = float(max_range)
        return (actual_value + max_range) / (2 * max_range)
