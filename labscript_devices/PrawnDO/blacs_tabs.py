#####################################################################
#                                                                   #
# /labscript_devices/PrawnDO/blacs_tabs.py                          #
#                                                                   #
# Copyright 2023, Philip Starkey, Carter Turnbaugh, Patrick Miller  #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from blacs.device_base_class import DeviceTab

class PrawnDOTab(DeviceTab):
    def initialise_GUI(self):
        do_prop = {}
        for i in range(0, 16):
            do_prop['do{:01d}'.format(i)] = {}
        self.create_digital_outputs(do_prop)

        def sort(channel):
            return int(channel.split('do')[-1])

        _, _, do_widgets = self.auto_create_widgets()
        self.auto_place_widgets(('Digital Outputs', do_widgets, sort))

        device = self.settings['connection_table'].find_by_name(self.device_name)

        self.com_port = device.properties['com_port']

        self.supports_remote_value_check(True)
        self.supports_smart_programming(True)

    
    def get_child_from_connection_table(self, parent_device_name, port):
        # all child direct outputs are actually connected to the internal device _PrawnDigitalOutputs
        # so we must look under that device for the port
        return self.connection_table.find_child(f'{self.device_name:s}__pod', port)


    def initialise_workers(self):
        self.create_worker(
            "main_worker",
            "labscript_devices.PrawnDO.blacs_workers.PrawnDOWorker",
            {
                'com_port': self.com_port,
            },
        )
        self.primary_worker = "main_worker"
