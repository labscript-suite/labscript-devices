from qtutils.qt.QtWidgets import QPushButton, QSizePolicy, QHBoxLayout, QSpacerItem, QSizePolicy as QSP
from blacs.tab_base_classes import Worker, define_state
from blacs.device_base_class import DeviceTab
from .logger_config import logger
from blacs.tab_base_classes import MODE_MANUAL

class BS_341ATab(DeviceTab):
    def initialise_GUI(self):

        connection_table = self.settings['connection_table']
        properties = connection_table.find_by_name(self.device_name).properties

        # Capabilities
        self.base_units = 'V'
        self.base_min = -24
        self.base_max = 24
        self.base_step = 1
        self.base_decimals = 3
        self.num_AO = 8 # or properties['num_AO']
                
        # Create AO Output objects
        ao_prop = {}
        for i in range(self.num_AO):
            if i == 0:
                ao_prop['channel %d' % i+1] = {
                    'base_unit': self.base_units,
                    'min': self.base_min,
                    'max': self.base_max,
                    'step': self.base_step,
                    'decimals': self.base_decimals,
                }
            else:
                ao_prop['channel %d' % i+1] = {
                    'base_unit': self.base_units,
                    'min': self.base_min - 10, #workaround defect
                    'max': self.base_max + 10,
                    'step': self.base_step,
                    'decimals': self.base_decimals,
                }
            
        # Create the output objects
        self.create_analog_outputs(ao_prop)
        
        # Create widgets for output objects
        widgets, ao_widgets,_ = self.auto_create_widgets()
        self.auto_place_widgets(("Analog Outputs", ao_widgets))

        # Add button to reprogramm device from manual mode
        self.send_button = QPushButton("Send to device")
        self.send_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.send_button.adjustSize()
        self.send_button.setStyleSheet("""
                    QPushButton {
                        border: 1px solid #B8B8B8;
                        border-radius: 3px;
                        background-color: #F0F0F0;
                        padding: 4px 10px;
                        font-weight: light;
                    }
                    QPushButton:hover {
                        background-color: #E0E0E0;
                    }
                    QPushButton:pressed {
                        background-color: #D0D0D0;
                    }
                """)
        self.send_button.clicked.connect(lambda: self.send_to_BS())

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
            'labscript_devices.BS_341A.BLACS_workers.BS_341AWorker',
            worker_kwargs,
        )
        self.primary_worker = "main_worker"
        
    @define_state(MODE_MANUAL, True)
    def send_to_BS(self):
        """Queue a manual send-to-device operation from the GUI.

            This function is triggered from the BLACS tab (by pressing a button)
            and runs in the main thread. It queues the `send2BS()` function to be
            executed by the worker.

            Used to reprogram the BS-1-10 device based on current front panel values.
            """
        try:
            yield(self.queue_work(self.primary_worker, 'send_to_BS', []))
        except Exception as e:
            logger.debug(f"Error by send work to worker(send_to_BS): \t {e}")
