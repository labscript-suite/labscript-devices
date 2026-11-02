"""
Emulate the serial port for the BS 34-1A.

You will create a virtual serial port using this script. This script will act as if it’s the BS 34-1A device. When you run the script, it will open a serial port (for example, /dev/pts/1) and allow other programs (such as your BLACS worker) to communicate with it.

The virtual serial port should stay open while the simulation is running, so other code that expects to interact with the serial device can do so just as if the actual device were connected.

Run following command in the corresponding folder.
    python3 -m BS_Series.testing.emulateSerPort
"""

import os, pty, threading, time
import sys

class BS_341AEmulator:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.master, self.slave = pty.openpty()
        self.running = False
        self.port_name = os.ttyname(self.slave)
        self.thread = threading.Thread(target=self._run)

    def start(self):
        self.running = True
        self.thread.start()
        if self.verbose:
            print("Starting BS 34-1A Emulator on virtual port: " + self.port_name)

    def stop(self):
        self.running = False
        self.thread.join()
        if self.verbose:
            print("Stopping BS 34-1A Emulator.")

    def _run(self):
        while self.running:
            try:
                command = self._read_command().decode().strip()
                if self.verbose:
                    print(f"Received: {command}")
                if command == "IDN":
                    self._respond("HV341 34 8 b\r")
                elif command.startswith("HV341 CH"):
                    _, channel, voltage = command.split()[:3]
                    self._respond(f"{channel} {voltage}\r")
                else:
                    self._respond("err\r")
            except Exception as e:
                self._respond("err\r")
            time.sleep(0.05)

    def _read_command(self):
        """ Reads the command until the '\r' character is encountered. """
        return b"".join(iter(lambda: os.read(self.master, 1), b"\r"))

    def _respond(self, message):
        os.write(self.master, message.encode())
        if self.verbose:
            print(f"Responded: {message.strip()}")


if __name__ == "__main__":
    emulator = BS_341AEmulator(verbose=True)
    emulator.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        emulator.stop()
        sys.exit(0)