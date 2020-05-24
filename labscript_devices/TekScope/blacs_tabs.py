from blacs.device_base_class import DeviceTab

class TekScopeTab(DeviceTab):
    def initialise_GUI(self):
        pass

    def initialise_workers(self):
        worker_initialisation_kwargs = self.connection_table.find_by_name(self.device_name).properties
        worker_initialisation_kwargs['addr'] = self.BLACS_connection
        self.create_worker(
            'main_worker',
            'labscript_devices.TekScope.blacs_workers.TekScopeWorker',
            worker_initialisation_kwargs,
        )
        self.primary_worker = 'main_worker'