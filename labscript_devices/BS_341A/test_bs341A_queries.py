import os
import pty
import time
import threading
import unittest
import serial

# Simulated serial device logic (used for testing)
def test_serial_emulator(master_fd):
    while True:
        command = read_command(master_fd).decode().strip()
        if command:
            print(f"[EMULATOR] Received command: {command}")
            if command == "IDN":
                response = "HV341 14 4 b\r"
            elif command.startswith("HV341 U"):
                response = "+12,345 V\r"
            elif command.startswith("HV341 I"):
                response = "-00,123 mA\r"
            elif command.startswith("HV341 Q"):
                response = "+12,345 V -00,123 mA\r"
            elif command.startswith("HV341 TEMP"):
                response = "TEMP 45.3°C\r"
            else:
                response = "err\r"
            os.write(master_fd, response.encode())
        time.sleep(0.1)

def read_command(master_fd):
    return b"".join(iter(lambda: os.read(master_fd, 1), b"\r"))

class TestBS110DeviceQueries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        master_fd, slave_fd = pty.openpty()
        cls.slave_name = os.ttyname(slave_fd)
        cls.master_fd = master_fd

        cls.emulator_thread = threading.Thread(target=test_serial_emulator, args=(master_fd,), daemon=True)
        cls.emulator_thread.start()

        cls.serial_conn = serial.Serial(cls.slave_name, baudrate=9600, timeout=1)

        class DummyWorker:
            device_serial = "HV341"
            port = cls.slave_name
            connection = cls.serial_conn
            device_voltage_range = 60.0
            def _scale_to_normalized(self, val, rng): return val / rng

        cls.worker = DummyWorker()

    def test_identify_query(self):
        self.worker.connection.write(b"IDN\r")
        response = self.worker.connection.readline().decode().strip()
        self.assertEqual(response, "HV341 14 4 b")

    def test_voltage_query(self):
        self.worker.connection.write(b"HV341 U01\r")
        response = self.worker.connection.readline().decode().strip()
        self.assertTrue(response.endswith("V"))
        voltage = float(response[:-1].replace(",", ".").strip())
        self.assertAlmostEqual(voltage, 12.345)

    def test_current_query(self):
        self.worker.connection.write(b"HV341 I01\r")
        response = self.worker.connection.readline().decode().strip()
        self.assertTrue(response.endswith("mA"))
        current = float(response[:-2].replace(",", ".").strip())
        self.assertAlmostEqual(current, -0.123)

    def test_vol_curr_query(self):
        self.worker.connection.write(b"HV341 Q01\r")
        response = self.worker.connection.readline().decode().strip()
        self.assertTrue(response.endswith("mA") and "V" in response)
        parts = response.split("V")
        voltage = float(parts[0].replace(",", ".").strip())
        current = float(parts[1].replace("mA", "").replace(",", ".").strip())
        self.assertAlmostEqual(voltage, 12.345)
        self.assertAlmostEqual(current, -0.123)

    def test_temperature_query(self):
        self.worker.connection.write(b"HV341 TEMP\r")
        response = self.worker.connection.readline().decode().strip()
        self.assertTrue(response.endswith("°C"))
        temperature = float(response.split()[1].replace("°C", ""))
        self.assertAlmostEqual(temperature, 45.3)

if __name__ == "__main__":
    unittest.main()
