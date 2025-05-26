"""
Emulate the serial port for the BS 34-1A.

You will create a virtual serial port using this script. This script will act as if it’s the BS 34-1A device. When you run the script, it will open a serial port (for example, /dev/pts/1) and allow other programs (such as your BLACS worker) to communicate with it.

The virtual serial port should stay open while the simulation is running, so other code that expects to interact with the serial device can do so just as if the actual device were connected.

Run following command in the corresponding folder.
    python3 -m BS_341A.emulateSerPort
"""

import os, pty
import time

def test_serial():
    """
    Initialise the serial port.
    prints the serial port to use.
    """
    master, slave = pty.openpty()
    port_name = os.ttyname(slave)
    print(f"For BS 34-1A use: {port_name}")

    while True:
        device_identity = "HV341 14 4 b\r"
        command = read_command(master).decode().strip()
        if command:
            print("command {}".format(command))
            if command == "IDN":
                response = device_identity.encode()
                os.write(master, response)
            elif command.startswith("HV341 CH"):
                device, channel, voltage = command.split()[:3]
                response = f"{channel} {voltage}\r"
                os.write(master, response.encode())
            else:
                response = f"err\r"
                os.write(master, response.encode())

        time.sleep(0.1)

def read_command(master):
    """ Reads the command until the '\r' character is encountered. """
    return b"".join(iter(lambda: os.read(master, 1), b"\r"))

if __name__ == "__main__":
    test_serial() 