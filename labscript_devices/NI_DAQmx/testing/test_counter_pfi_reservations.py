import os
import sys
import types
import unittest

os.environ.setdefault('READTHEDOCS', 'True')

import numpy as np

from labscript import LabscriptError
from labscript_devices.NI_DAQmx.labscript_devices import NI_DAQmx


class CounterStub:
    def __init__(self, name='counter', edge=None, gate=None, sample=None):
        self.name = name
        self.edge_terminal = edge
        self.gate_terminal = gate
        self.sample_terminal = sample
        self.acquisitions = []


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

    def test_counter_declaration_table_does_not_require_acquire(self):
        device = self.make_device()
        table = device._make_counter_declaration_table(
            {
                'ctr0': CounterStub(
                    name='counts', edge='PFI0', gate=None, sample='PFI1'
                )
            }
        )
        self.assertEqual(len(table), 1)
        self.assertEqual(table['name'][0], b'counts')
        self.assertEqual(table['connection'][0], b'ctr0')
        self.assertEqual(table['edge terminal'][0], b'PFI0')
        self.assertEqual(table['gate terminal'][0], b'')
        self.assertEqual(table['sample terminal'][0], b'PFI1')


def import_counter_worker():
    pythonlib = types.ModuleType('pythonlib')
    data_saver = types.ModuleType('pythonlib.data_saver')
    online_monitor = types.ModuleType('pythonlib.online_monitor')

    class DataSaver:
        pass

    class OnlineMonitor:
        pass

    data_saver.DataSaver = DataSaver
    online_monitor.OnlineMonitor = OnlineMonitor
    sys.modules.setdefault('pythonlib', pythonlib)
    sys.modules.setdefault('pythonlib.data_saver', data_saver)
    sys.modules.setdefault('pythonlib.online_monitor', online_monitor)

    from labscript_devices.NI_DAQmx.blacs_workers import NI_DAQmxCounterWorker

    return NI_DAQmxCounterWorker


class TestManualCounterProcessing(unittest.TestCase):
    def test_manual_counter_values_wait_for_two_counts_without_previous(self):
        worker_class = import_counter_worker()
        worker = object.__new__(worker_class)
        values, previous = worker._manual_counter_values(
            np.array([5], dtype=np.uint32), None, 10.0
        )
        self.assertEqual(values.tolist(), [])
        self.assertEqual(previous, 5)

    def test_manual_counter_values_use_previous_count_and_scale(self):
        worker_class = import_counter_worker()
        worker = object.__new__(worker_class)
        values, previous = worker._manual_counter_values(
            np.array([8, 11], dtype=np.uint32), 5, 20.0
        )
        self.assertEqual(values.tolist(), [60.0, 60.0])
        self.assertEqual(previous, 11)


if __name__ == '__main__':
    unittest.main()
