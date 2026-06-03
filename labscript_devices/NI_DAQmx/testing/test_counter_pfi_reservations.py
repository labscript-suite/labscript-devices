import os
import sys
import types
import unittest
import threading

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
        self.assertTrue(table['manual enabled'][0])
        self.assertEqual(table['manual sample clock'][0], b'connection_table')
        self.assertEqual(table['manual rate'][0], 10.0)
        self.assertEqual(table['manual buffer size'][0], 1024)
        self.assertEqual(table['manual polling interval'][0], 0.1)

    def test_buffered_counter_acquisitions_cannot_duplicate_ctr(self):
        device = self.make_device()
        counter = CounterStub(name='counts', edge='PFI0', sample='PFI1')
        counter.acquisitions = [
            {
                'label': 'first',
                'max_sampling_rate': 10.0,
                'buffer_size': 10,
                'polling_interval': 0.1,
            },
            {
                'label': 'second',
                'max_sampling_rate': 10.0,
                'buffer_size': 10,
                'polling_interval': 0.1,
            },
        ]
        with self.assertRaises(LabscriptError):
            device._make_counter_input_table({'ctr0': counter})


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


def import_counter_tab():
    blacs = types.ModuleType('blacs')
    device_base_class = types.ModuleType('blacs.device_base_class')
    tab_base_classes = types.ModuleType('blacs.tab_base_classes')
    qtutils = types.ModuleType('qtutils')
    qtutils_qt = types.ModuleType('qtutils.qt')

    class DeviceTab:
        pass

    def define_state(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

    device_base_class.DeviceTab = DeviceTab
    tab_base_classes.MODE_MANUAL = 1
    tab_base_classes.define_state = define_state
    qtutils_qt.QtWidgets = object()

    sys.modules.setdefault('blacs', blacs)
    sys.modules.setdefault('blacs.device_base_class', device_base_class)
    sys.modules.setdefault('blacs.tab_base_classes', tab_base_classes)
    sys.modules.setdefault('qtutils', qtutils)
    sys.modules.setdefault('qtutils.qt', qtutils_qt)

    from labscript_devices.NI_DAQmx.blacs_tabs import NI_DAQmxTab

    return NI_DAQmxTab


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

    def test_manual_counter_start_rejects_active_sample_clock_as_input(self):
        worker_class = import_counter_worker()
        worker = object.__new__(worker_class)
        worker.tasklock = threading.RLock()
        worker.manual_counters = {
            'existing': {
                'counter': {'connection': 'ctr1'},
                'sample_clock': 'connection_table',
            }
        }
        with self.assertRaises(RuntimeError):
            worker.start_manual_counter(
                'new',
                {'connection': 'ctr0', 'edge': 'PFI0', 'gate': '', 'sample': ''},
                {
                    'sample_clock': 'ctr1',
                    'rate': 10.0,
                    'buffer_size': 1024,
                    'polling_interval': 0.1,
                    'multiplication_factor': 1.0,
                    'average_count': 10,
                    'udp_host': '127.0.0.1',
                    'udp_port': 9000,
                },
            )

    def test_manual_counter_start_rejects_active_sample_clock_as_output(self):
        worker_class = import_counter_worker()
        worker = object.__new__(worker_class)
        worker.tasklock = threading.RLock()
        worker.manual_counters = {
            'existing': {
                'counter': {'connection': 'ctr0'},
                'sample_clock': 'ctr1',
            }
        }
        with self.assertRaises(RuntimeError):
            worker.start_manual_counter(
                'new',
                {'connection': 'ctr1', 'edge': 'PFI0', 'gate': '', 'sample': 'PFI1'},
                {
                    'sample_clock': 'connection_table',
                    'rate': 10.0,
                    'buffer_size': 1024,
                    'polling_interval': 0.1,
                    'multiplication_factor': 1.0,
                    'average_count': 10,
                    'udp_host': '127.0.0.1',
                    'udp_port': 9000,
                },
            )

    def test_manual_counter_monitor_yields_when_no_active_counters(self):
        tab_class = import_counter_tab()
        tab = object.__new__(tab_class)
        tab.manual_counter_active = set()
        calls = []

        def queue_work(worker, method, *args):
            calls.append((worker, method, args))
            return calls[-1]

        tab.queue_work = queue_work
        generator = tab.manual_counter_monitor()

        self.assertEqual(next(generator), ("counter_worker", "noop", ()))
        self.assertEqual(calls, [("counter_worker", "noop", ())])
        with self.assertRaises(StopIteration):
            next(generator)

    def test_manual_counter_monitor_handles_baseline_only_read(self):
        tab_class = import_counter_tab()
        tab = object.__new__(tab_class)
        tab.manual_counter_active = {'counts'}
        texts = {}

        class Label:
            def __init__(self, name):
                self.name = name

            def setText(self, text):
                texts[self.name] = text

        tab.manual_counter_widgets = {
            'counts': {
                'latest': Label('latest'),
                'moving_average': Label('moving_average'),
                'status': Label('status'),
            }
        }

        def queue_work(worker, method, *args):
            return {'status': 'running', 'samples_read': 1}

        tab.queue_work = queue_work
        generator = tab.manual_counter_monitor()

        self.assertEqual(next(generator), {'status': 'running', 'samples_read': 1})
        with self.assertRaises(StopIteration):
            generator.send({'status': 'running', 'samples_read': 1})
        self.assertEqual(texts, {'status': 'running'})


if __name__ == '__main__':
    unittest.main()
