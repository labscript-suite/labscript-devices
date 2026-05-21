import os
import unittest

os.environ.setdefault('READTHEDOCS', 'True')

from labscript import LabscriptError
from labscript_devices.NI_DAQmx.labscript_devices import NI_DAQmx


class CounterStub:
    def __init__(self, edge=None, gate=None, sample=None):
        self.edge_terminal = edge
        self.gate_terminal = gate
        self.sample_terminal = sample


class TestCounterPFIReservations(unittest.TestCase):
    def make_device(self, PFI_connections=None):
        device = object.__new__(NI_DAQmx)
        device.name = 'DevTest'
        device.PFI_connections = PFI_connections or {}
        return device

    def test_counter_reserves_mapped_dio_line(self):
        device = self.make_device({'PFI0': 'port0/line0'})
        reserved = device._check_counter_dio_conflicts(
            {'port0/line1': object()},
            {'ctr0': CounterStub(edge='PFI0')},
        )
        self.assertEqual(reserved, {'port0/line0': 'PFI0'})

    def test_counter_conflicts_with_declared_digital_output(self):
        device = self.make_device({'PFI0': 'port0/line0'})
        with self.assertRaises(LabscriptError):
            device._check_counter_dio_conflicts(
                {'port0/line0': object()},
                {'ctr0': CounterStub(edge='PFI0')},
            )

    def test_missing_pfi_mapping_raises(self):
        device = self.make_device()
        with self.assertRaises(LabscriptError):
            device._check_counter_dio_conflicts(
                {},
                {'ctr0': CounterStub(edge='PFI0')},
            )


if __name__ == '__main__':
    unittest.main()
