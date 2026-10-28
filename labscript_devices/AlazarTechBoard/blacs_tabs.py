# A labscript device class for data acquisition boards made by Alazar Technologies Inc (ATS)
# Hacked up from NIboard.py by LDT 2017-01-26
#
# Copyright (c) Monash University 2017
from blacs.device_base_class import DeviceTab


# A BLACS tab for a purely remote device which does not need configuration of parameters in BLACS


class GuilessTab(DeviceTab):
    def initialise_GUI(self):
        pass

    def get_save_data(self):
        return {}

    def restore_save_data(self, save_data):
        pass

    def initialise_workers(self):
        # Create and set the primary worker
        self.create_worker("main_worker", "labscript_devices.AlazarTechBoard.blacs_workers.GuilessWorker", {})
        self.primary_worker = "main_worker"
