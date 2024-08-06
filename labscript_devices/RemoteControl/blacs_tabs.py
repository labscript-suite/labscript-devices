from labscript_utils import dedent
from qtutils.qt import QtWidgets, QtGui, QtCore
from qtutils import qtlock

from blacs.device_base_class import (
    DeviceTab,
    define_state,
    MODE_BUFFERED,
    MODE_MANUAL,
    MODE_TRANSITION_TO_BUFFERED,
    MODE_TRANSITION_TO_MANUAL,
)

import threading
import zmq
import time

class DynamicStackedWidget(QtWidgets.QStackedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.currentChanged.connect(self.adjustSize)

    def sizeHint(self):
        if self.currentWidget():
            return self.currentWidget().sizeHint()
        return super().sizeHint()

    def minimumSizeHint(self):
        if self.currentWidget():
            return self.currentWidget().minimumSizeHint()
        return super().minimumSizeHint()

    def adjustSize(self):
        self.setMinimumSize(self.minimumSizeHint())
        super().adjustSize()
        if self.parent() and isinstance(self.parent(), QtWidgets.QWidget):
            self.parent().adjustSize()

class FailureButton(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.button = QtWidgets.QPushButton("CONNECTION FAILED, CLICK TO RECONNECT")
        self.button.setStyleSheet("""
            QPushButton {
                color: white;
                font-weight: bold;
                background-color: #ff6666;
                border: 2px solid #ff4d4d;
                border-radius: 10px;
                padding: 20px 40px;
                font-size: 18px;
            }
            QPushButton:hover {
                background-color: #ff4d4d;
            }
            QPushButton:pressed {
                background-color: #ff3333;
            }
        """)

        layout = QtWidgets.QVBoxLayout()
        layout.setAlignment(QtCore.Qt.AlignCenter)
        layout.addStretch(1)
        layout.addWidget(self.button, alignment=QtCore.Qt.AlignCenter)
        layout.addStretch(1)

        self.setLayout(layout)

    def connect_clicked(self, slot):
        self.button.clicked.connect(slot)

class RemoteControlTab(DeviceTab):
    def create_centered_button_widget(self, button):
        layout = QtWidgets.QVBoxLayout()
        layout.addStretch()
        layout.addWidget(button, alignment=QtCore.Qt.AlignCenter)
        layout.addStretch()
        
        widget = QtWidgets.QWidget()
        widget.setLayout(layout)
        return widget
    
    def initialise_GUI(self):
        connection_table = self.settings['connection_table']
        device = connection_table.find_by_name(self.device_name)
        self.properties = device.properties

        self.mock = self.properties['mock']
        self.host = self.properties['host']
        self.reqrep_port = self.properties['reqrep_port']
        self.pubsub_port = self.properties['pubsub_port']

        self.reqrep_connected = False
        self.pubsub_connected = False

        self.child_output_devices = []
        self.child_monitor_devices = []
        self.child_output_connections = []
        self.child_monitor_connections = []

        for child_device in device.child_list.values():
            if child_device.device_class == "RemoteAnalogOut":
                self.child_output_devices.append(child_device)
                self.child_output_connections.append(child_device.parent_port)
            elif child_device.device_class == "RemoteAnalogMonitor":
                self.child_monitor_devices.append(child_device)
                self.child_monitor_connections.append(child_device.parent_port)
            else:
                # throw an error
                pass

        # Remote Output Value Widgets
        AO_prop = {}
        for analog_out_device in self.child_output_devices:
            child_properties = analog_out_device._properties
            min_val, max_val = child_properties["limits"]
            AO_prop[analog_out_device.parent_port] = {
                'base_unit': child_properties["units"],
                'min': min_val,
                'max': max_val,
                'step': child_properties["step_size"],
                'decimals': child_properties["decimals"],
            }
        self.create_analog_outputs(AO_prop)
        _, self.AO_widgets, _ = self.auto_create_widgets()
        self.ao_toolpalette_widget = self.auto_place_widgets(("Analog Outputs", self.AO_widgets))

        # Remote Monitor Value Widgets
        AM_prop = {}
        for analog_monitor_device in self.child_monitor_devices:
            child_properties = analog_monitor_device._properties
            min_val, max_val = child_properties["limits"]
            AM_prop[analog_monitor_device.parent_port] = {
                'base_unit': child_properties["units"],
                'min': min_val,
                'max': max_val,
                'step': child_properties["step_size"],
                'decimals': child_properties["decimals"],
            }
        self.create_analog_outputs(AM_prop)
        _, self.AM_widgets, _ = self.create_subset_widgets(AM_prop)
        self.am_toolpalette_widget = self.auto_place_widgets(("Analog Monitors", self.AM_widgets))
        
        for _, widget in self.AM_widgets.items():
            widget.setEnabled(False)

        # Connectivity buttons
        self.reconnect_reqrep_button = QtWidgets.QPushButton("Click Here to Reconnect\nREQ-REP socket")
        self.reconnect_reqrep_button.setStyleSheet("background-color: #ffcccc;")
        self.reconnect_reqrep_button.clicked.connect(self.reconnect_reqrep)
        self.reconnect_reqrep_button.hide()

        self.reconnect_pubsub_button = QtWidgets.QPushButton("Click Here to Reconnect\nPUB-SUB socket")
        self.reconnect_pubsub_button.setStyleSheet("background-color: #ffcccc;")
        self.reconnect_pubsub_button.clicked.connect(self.reconnect_pubsub)
        self.reconnect_pubsub_button.hide()

        # Set up the layout
        self.main_gui_layout = self.get_tab_layout()

        # Placeholder widgets to hold either the toolpalette or the button
        # Use the dynamic class to adjust the size of the placeholder widget based
        # on the size of the toolpalette/button
        self.ao_placeholder = DynamicStackedWidget()
        self.am_placeholder = DynamicStackedWidget()
        
        self.ao_placeholder.addWidget(self.ao_toolpalette_widget)
        self.ao_placeholder.addWidget(self.reconnect_reqrep_button)
        self.am_placeholder.addWidget(self.am_toolpalette_widget)
        self.am_placeholder.addWidget(self.reconnect_pubsub_button)
        self.main_gui_layout.insertWidget(0, self.ao_placeholder)
        self.main_gui_layout.insertWidget(1, self.am_placeholder)   

        # Enable Comms Checkbox
        self.comms_check_box = QtWidgets.QCheckBox("Disable Input")
        self.main_gui_layout.addWidget(self.comms_check_box)
        self.comms_check_box.toggled.connect(self.on_checkbox_toggled)

        # Hide the UI until after trying to establish connection
        self.ao_placeholder.hide()
        self.am_placeholder.hide()
        self.comms_check_box.hide()
        
        # Connection Failed Button
        # TODO: define the failed button layout in the QT designer application and store in .ui file
        self.failed_button = FailureButton()
        self.failed_button.connect_clicked(lambda: self.connect_to_remote())
        self.main_gui_layout.addWidget(self.failed_button)
        self.failed_button.hide()

    def initialise_workers(self):
        # Create the worker
        self.create_worker(
            "main_worker",
            "labscript_devices.RemoteControl.blacs_workers.RemoteControlWorker",
            {
                "mock": self.mock,
                "host": self.host,
                "port": self.reqrep_port,
                "child_output_connections": self.child_output_connections,
                "child_monitor_connections": self.child_monitor_connections,
            }
        )
        self.primary_worker = "main_worker"

        if self.mock:
            self.reqrep_connected = True
            self.manual_remote_polling()
        else:
            self.connect_to_remote()
    
    # DEPRECATE
    def manual_remote_polling(self, enable_comms_state=False):    
        # Start up the remote value polling
        self.statemachine_timeout_add(500, self.status_monitor)
        self.statemachine_timeout_add(5000, self.check_remote_values) 

        if enable_comms_state:
            self.statemachine_timeout_remove(self.check_remote_values_allowed)  
            self.statemachine_timeout_add(5000, self.check_remote_values)  
        else:
            self.statemachine_timeout_remove(self.check_remote_values) 
            # start up the remote value check which gracefully updates the FPV 
            self.statemachine_timeout_add(500, self.check_remote_values_allowed)  

    # DEPRECATE
    @define_state(
        MODE_MANUAL|MODE_BUFFERED|MODE_TRANSITION_TO_BUFFERED|MODE_TRANSITION_TO_MANUAL,True,
    )
    def status_monitor(self):
        response = yield (
            self.queue_work(self.primary_worker, "check_status")
        )
        for connection, value in response.items():
            self._AO[connection].set_value(float(value), program=False, update_gui=True)
        return response
    
    @define_state(MODE_MANUAL, True)
    def on_checkbox_toggled(self, state):
        with qtlock:
            for widget in self.AO_widgets.values():
                widget.setEnabled(not state)

        self.statemachine_timeout_remove(self.check_remote_values)  
        if state:
            # If checkbox toggled (no comms) we allow/expect remote values to change.
            # Check them more frequently
            self.statemachine_timeout_add(500, self.check_remote_values, True)  
        else:
            # If checkbox toggled (comms we expect no mistmatch
            # Check them less frequently
            self.statemachine_timeout_add(5000, self.check_remote_values, False)

        kwargs = {'enable_comms': not state}
        yield(self.queue_work(self.primary_worker, 'update_settings', **kwargs))
    
    def reconnect_reqrep(self):
        self.connect_to_reqrep()
        self.update_gui_status()
    
    def reconnect_pubsub(self):
        self.connect_to_pubsub()
        self.update_gui_status()
        
    def connect_to_remote(self):
        self.connect_to_reqrep()
        self.connect_to_pubsub()

    @define_state(MODE_MANUAL, True)
    def connect_to_reqrep(self):
        self.reqrep_connected = yield(self.queue_work(self.primary_worker, 'connect_to_remote'))
        self.update_gui_status()

    def connect_to_pubsub(self):
        self.pubsub_connected = False
        self.heartbeat_thread = threading.Thread(target=self.heartbeat_subscriber)
        self.heartbeat_thread.daemon = True
        self.heartbeat_thread.start()

    def heartbeat_subscriber(self):
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        socket.connect(f"tcp://{self.host}:{self.pubsub_port}")
        socket.setsockopt_string(zmq.SUBSCRIBE, "heartbeat")

        poller = zmq.Poller()
        poller.register(socket, zmq.POLLIN)

        while True:
            try:
                socks = dict(poller.poll(2000))  # 5000 ms timeout
                if socket in socks and socks[socket] == zmq.POLLIN:
                    message = socket.recv_string(zmq.NOBLOCK)
                    if message == "heartbeat":
                        if not self.pubsub_connected:
                            self.pubsub_connected = True
                            self.update_gui_status()
                            self.logger.debug("Pub-sub connection established")
                            self.start_subscriber()
                else:
                    if self.pubsub_connected:
                        self.pubsub_connected = False
                        self.update_gui_status()
                        self.logger.error("Heartbeat timeout, pub-sub connection lost")
                    break
            except zmq.ZMQError as e:
                self.logger.error(f"ZMQ E rror in heartbeat subscriber: {e}")
                self.pubsub_connected = False
                self.update_gui_status()
                break
            
            time.sleep(1)

    def start_subscriber(self):
        if not hasattr(self, 'subscriber_thread') or not self.subscriber_thread.is_alive():
            self.subscriber_thread = threading.Thread(target=self.subscriber_loop)
            self.subscriber_thread.daemon = True
            self.subscriber_thread.start()

    def subscriber_loop(self):
        context = zmq.Context()
        subscribers = {}
        poller = zmq.Poller()

        try:
            for connection in self.child_monitor_connections:
                subscriber = context.socket(zmq.SUB)
                subscriber.connect(f"tcp://{self.host}:{self.pubsub_port}")
                subscriber.setsockopt_string(zmq.SUBSCRIBE, connection)
                subscribers[connection] = subscriber
                poller.register(subscriber, zmq.POLLIN)

            while self.pubsub_connected:
                try:
                    socks = dict(poller.poll(timeout=100))
                    for subscriber in socks:
                        message = subscriber.recv_string()
                        connection, value = message.split(" ", 1)
                        self.update_gui_with_message(connection, value)

                except zmq.ZMQError as e:
                    self.logger.error(f"ZMQ error in subscriber loop: {e}")

        finally:
            for subscriber in subscribers.values():
                subscriber.close()
            self.update_gui_status()
            context.term()
    
    def update_gui_with_message(self, connection, value):
        if connection in self.AM_widgets:
                self._AO[connection].set_value(float(value), program=False)

    def update_gui_status(self):
        with qtlock:
            if not (self.reqrep_connected or self.pubsub_connected):
                # No connection
                self.failed_button.show()

                self.ao_placeholder.hide()
                self.am_placeholder.hide()
                self.comms_check_box.hide()
            else:
                if self.reqrep_connected and self.pubsub_connected: # Fully connected
                    # Check if remote setpoints differ from front panel values every 5 seconds
                    self._can_check_remote_values = True
                    self.statemachine_timeout_add(5000, self.check_remote_values) 
                    
                    self.ao_placeholder.setCurrentWidget(self.ao_toolpalette_widget)
                    self.am_placeholder.setCurrentWidget(self.am_toolpalette_widget)
                    self.comms_check_box.show()
                elif self.reqrep_connected:
                    # Check if remote setpoints differ from front panel values every 5 seconds
                    self._can_check_remote_values = True
                    self.statemachine_timeout_add(5000, self.check_remote_values) 
                    
                    self.ao_placeholder.setCurrentWidget(self.ao_toolpalette_widget)
                    self.am_placeholder.setCurrentWidget(self.reconnect_pubsub_button)
                    self.comms_check_box.show()
                elif self.pubsub_connected:
                    self.ao_placeholder.setCurrentWidget(self.reconnect_reqrep_button)
                    self.am_placeholder.setCurrentWidget(self.am_toolpalette_widget)
                    self.comms_check_box.hide()       
                self.failed_button.hide()
                self.ao_placeholder.show()
                self.am_placeholder.show()