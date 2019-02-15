from __future__ import division, unicode_literals, print_function, absolute_import
from labscript_utils import PY2
if PY2:
    str = unicode
from blacs.device_base_class import DeviceTab

class TekScopeTab(DeviceTab):
    def initialise_GUI(self):
        self.address = self.BLACS_connection
        connection_object = self.settings['connection_table'].find_by_name(self.device_name)
        self.connection_table_properties = connection_object.properties

    def initialise_workers(self):
        worker_initialisation_kwargs = {'addr': self.address}
        for kwarg in ['termination', 'preamble_string']:
            worker_initialisation_kwargs[kwarg] = self.connection_table_properties[kwarg]
        self.create_worker(
            'main_worker',
            'labscript_devices.TekScope.blacs_worker.TekScopeWorker',
            worker_initialisation_kwargs,
        )
        self.primary_worker = 'main_worker'