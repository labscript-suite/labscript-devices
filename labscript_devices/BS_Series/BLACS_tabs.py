from qtutils.qt.QtWidgets import QPushButton, QSizePolicy, QHBoxLayout, QSpacerItem, QSizePolicy as QSP
from blacs.tab_base_classes import Worker, define_state
from blacs.device_base_class import DeviceTab
from .logger_config import logger
from blacs.tab_base_classes import MODE_MANUAL
from .utils import _create_button

class BS_Tab(DeviceTab):
    def initialise_GUI(self):

        # Capabilities
        self.base_units = 'V'
        self.base_min = -24 # Depends on channel
        self.base_max = 24 # Depends on channel
        self.base_step = 1
        self.base_decimals = 3
        self.num_AO = 8
                
        # Create AO Output objects
        ao_prop = {}
        for i in range(1, int(self.num_AO) + 1):
            if i == 1:
                ao_prop['CH0%d' % i] = {
                    'base_unit': self.base_units,
                    'min': self.base_min,
                    'max': self.base_max,
                    'step': self.base_step,
                    'decimals': self.base_decimals,
                }
            else:
                ao_prop['CH0%d' % i] = {
                    'base_unit': self.base_units,
                    'min': -34.560, # workaround defect
                    'max': 34.560,
                    'step': self.base_step,
                    'decimals': self.base_decimals,
                }
            
        # Create and save AO objects
        self.create_analog_outputs(ao_prop)
        
        # Create widgets for AO objects
        widgets, ao_widgets,_ = self.auto_create_widgets()
        self.auto_place_widgets(("Analog Outputs", ao_widgets))

        # Create buttons to send-to-device
        self.send_button = _create_button("Send to device", self.send_to_BS)

        # Add centered layout to center the button
        center_layout = QHBoxLayout()
        center_layout.addStretch()
        center_layout.addWidget(self.send_button)
        center_layout.addStretch()

        # Add center layout on device layout
        self.get_tab_layout().addLayout(center_layout)

        self.supports_remote_value_check(False)
        self.supports_smart_programming(False)
        
    
    def initialise_workers(self):
        # Get properties from connection table.
        device = self.settings['connection_table'].find_by_name(self.device_name)
        if device is None:
            raise ValueError(f"Device '{self.device_name}' not found in the connection table.")
           
        # look up the port and baud in the connection table
        port = device.properties["port"]
        baud_rate = device.properties["baud_rate"]
        num_AO = device.properties['num_AO']
        worker_kwargs = {"name": self.device_name + '_main',
                         "port": port,
                         "baud_rate": baud_rate,
                         "num_AO": num_AO
                         }

        # Start a worker process 
        self.create_worker(
            'main_worker',
            'labscript_devices.BS_Series.BLACS_workers.BS_Worker',
            worker_kwargs,
        )
        self.primary_worker = "main_worker"
        
    @define_state(MODE_MANUAL, True)
    def send_to_BS(self):
        """Queue a manual send-to-device operation from the GUI.

            This function is triggered from the BLACS tab (by pressing a button)
            and runs in the main thread. It queues the `send_to_BS()` function to be
            executed by the worker.

            Used to reprogram the device based on current front panel values.
            """
        try:
            yield(self.queue_work(self.primary_worker, 'send_to_BS', []))
        except Exception as e:
            logger.debug(f"Error by send work to worker(send_to_BS): \t {e}")
