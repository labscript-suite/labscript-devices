import serial
import time
import serial.tools.list_ports

# dmesg | grep tty
# ls /dev/tty*
# lsusb

def check_ports():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        print(f"Port: {port.device}, Description: {port.description}")


port = '/dev/ttyUSB0'
baud_rate = 9600
timeout = 2

try:
    ser = serial.Serial(port, baud_rate, timeout=timeout)
    print(f"Connected to {port} at {baud_rate} baud")

    while True:
        cmd = input("Enter command (or type 'exit' to quit): ")
        cms = cmd + '\r'
        if cmd.lower() == 'exit':
            print("Exiting...")
            break

        # Send the command with carriage return, modify if your device uses something else
        ser.write((cmd + "\r").encode())
        time.sleep(0.5)  # Wait a bit for the device to respond

        # Read all available lines (or just one line if you prefer)
        response = ser.readline().decode().strip()
        print("Device response:", response)

    ser.close()

except serial.SerialException as e:
    print(f"Serial error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")