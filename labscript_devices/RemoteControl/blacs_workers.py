from blacs.tab_base_classes import Worker
import numpy as np
import labscript_utils.h5_lock
import h5py
import labscript_utils.properties
import zmq
import json

from labscript_utils.ls_zprocess import Context
from labscript_utils.shared_drive import path_to_local
from labscript_utils.properties import set_attributes

class RemoteCommunication:
    """
    A class for handling remote communication with a device.

    This class can operate in two modes:
    - Mock mode: Simulates communication for testing purposes.
    - Actual mode: Communicates with a remote server using ZMQ.

    JSON Structure:
    ----------------
    Requests:
    {
        "action": <string>,         # The action to be performed (e.g., "PROGRAM_MANUAL", "CHECK_STATUS").
        "connection": <string>,     # The identifier for the connection.
        "value": <any>              # The value to be programmed (optional, depends on action).
    }

    Responses:
    {
        "status": <string>,         # Status of the request (e.g., "SUCCESS", "ERROR").
        "message": <string>,        # Error or informational message (optional).
        "value": <any>              # The value from the remote device (optional, depends on action).
    }

    Example Request:
    {
        "action": "PROGRAM_MANUAL",
        "connection": "laser_raster_x_coord",
        "value": 123.45
    }

    Example Response:
    {
        "status": "SUCCESS",
        "value": 123.45
    }
    """
    def __init__(self, host=None, port=None, logger=None, child_connections=None, mock=False):
        self.mock = mock
        self.logger = logger
        self.child_connections = child_connections
        self.connected = False
        
        if self.mock:
            self.logger.debug("Starting remote communication using a mock server")
            self.dummy_values = {connection: np.random.uniform(0.1, 0.2) for connection in self.child_connections}
        else:
            self.context = zmq.Context()
            self.host = host
            self.port = port
    
    def connect_to_remote(self, timeout=1000):
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(f"tcp://{self.host}:{self.port}")
        
        self.socket.setsockopt(zmq.SNDTIMEO, timeout)
        self.socket.setsockopt(zmq.RCVTIMEO, timeout)

        self.logger.debug(f"TRYING TO SET UP CONNECTION, tcp://{self.host}:{self.port}")
        
        message = {"action": "HELLO", "connection": ""}
        
        response = self.send_request(message)
        if response is None:
            self.logger.debug("Connection setup failed or timed out.")
            self.socket.close()
            self.connected = False
        else:
            self.logger.debug(f"Connection Successful. Got response {response}")
            self.connected = True
        
        return self.connected
    
    def send_request(self, message):
        """
        Sends a request json message and returns the response.

        Args:
            message (dict): The request message to send as a json.

        Returns:
            dict: The response message.
        """
        if self.mock:
            # send message as a json
            response_json = self.mock_request_handler(json.dumps(message)) 
            return json.loads(response_json)
        else:
            try:
                self.socket.send_json(message)
                return self.socket.recv_json()
            except zmq.ZMQError as e:
                self.logger.error(f"Error during send/receive: {e}")
                if e.errno == zmq.EAGAIN:
                    if self.connected:
                        # The server has been disconnected after having been established previously
                        raise Exception("The server has been disconnected. Please refresh tab")
                else:
                    raise Exception(f"The remote communication has failed due to: {e}")

    def program_value(self, connection, value):
        message = {"action": "PROGRAM_VALUE", "connection": connection, "value": value}
        self.logger.debug(f"programming value with message: {message}")
        return self.send_request(message)

    def check_remote_value(self, connection):
        message = {"action": "CHECK_VALUE", "connection": connection}
        return self.send_request(message)
    
    def mock_request_handler(self, message_json):
        message = json.loads(message_json)

        action = message.get("action")
        connection = message.get("connection")
        value = message.get("value")

        if action == "PROGRAM_VALUE":
            self.logger.debug(f"Programming remote device with manual value: {value}")
            self.dummy_values[connection] = value
            # the corresponding monitor connection should also be updated here
            return json.dumps({"status": "SUCCESS"})
        elif action == "CHECK_VALUE":
            return json.dumps({"status": "SUCCESS", "value": self.dummy_values[connection]})
        elif action == "CHECK_MONITOR":
            rand_val = np.random.uniform(1, 10)
            self.dummy_values[connection] = rand_val
            return json.dumps({"status": "SUCCESS", "value": rand_val})
        else:
            return json.dumps({"status": "ERROR", "message": "Invalid action"})
        
class RemoteControlWorker(Worker):
    """
    A worker class for handling remote control operations.

    This class interfaces with the RemoteCommunication class to send commands and receive responses
    from a remote device.
    """
    def init(self):
        self.enable_comms = True
        self.h5_filepath = None

        self.child_connections = self.child_output_connections + self.child_monitor_connections

        self.remote_comms = RemoteCommunication(
            host=self.host, 
            port=self.port, 
            logger=self.logger, 
            child_connections=self.child_connections, 
            mock=self.mock
        )

        self.initial_monitor_values = {}

    def connect_to_remote(self):
        return self.remote_comms.connect_to_remote()
    
    def update_settings(self, enable_comms):
        self.enable_comms = enable_comms

    def handle_response(self, response):
        if response["status"] == "SUCCESS":
            return
        elif response["status"] == "ERROR":
            raise Exception('Error response from server: ' + str(response["message"]))
        elif response["status"] != "SUCCESS":
            raise Exception('invalid status response from server: ' + str(response["status"]))

    def check_all_remote_values(self):
        """
        Checks the remote values for ALL child connections to keep the front panel 
        up-to-date after manual programming 

        Returns:
            dict: A dictionary of remote values.
        """
        if not self.remote_comms.connected:
            return

        remote_values = {}
        for connection in self.child_connections:
            response = self.remote_comms.check_remote_value(connection)
            self.handle_response(response)
            remote_values[connection] = float(response["value"])
        return remote_values
    
    def check_remote_values(self):
        """
        Checks the remote values for all child OUTPUT connections.

        `check_remote_values` is a worker task for the `tab.check_remote_values` to check for
        remote updates of the Analog Output Setpoints

        Returns:
            dict: A dictionary of remote ouput values.
        """
        if not self.remote_comms.connected:
            return False
        
        def check_output_values():
            if len(self.child_output_connections) == 0:
                return None
            remote_values = {}
            for connection in self.child_output_connections:
                response = self.remote_comms.check_remote_value(connection)
                self.handle_response(response)
                remote_values[connection] = float(response["value"])
            return remote_values
        
        return check_output_values()
    
    # DEPRECATE check_status and add check_monitor_values()
    def check_status(self):
        """
        Checks the remote values of the child MONITOR connections.
        
        `check_status` is a worker task for the `tab.state_monitor` function that is used to
        store the most up to date value of the Analog Monitors 
        """
        if not self.remote_comms.connected:
            return

        def check_monitor_values():
            responses = {}
            for connection in self.child_monitor_connections:
                response = self.remote_comms.check_remote_value(connection)
                self.handle_response(response)
                self.logger.debug(f"recieved response {response}")
                responses[connection] = float(response["value"])
            return responses
        
        return check_monitor_values()

    def shutdown(self):
        # close the socket here
        pass

    def program_manual(self, front_panel_values):
        if not self.remote_comms.connected:
            return {}

        for connection in self.child_output_connections:
            response = self.remote_comms.program_value(connection, front_panel_values[connection])
            self.handle_response(response)
        # No need to return values to coerce front_panel_values since any changes to remote values
        # will be communicated through asynchronous PUB-SUB communication
        return {}

    def transition_to_buffered(self, device_name, h5_filepath, front_panel_values, fresh):
        if not self.enable_comms:
            return {}
        with h5py.File(h5_filepath, 'r') as f:
            group = f['devices'][self.device_name]
            if not 'remote_device_operation' in group:
                return {}

            if not self.remote_comms.connected:
                raise Exception("""Cannot program remote device when remote connection is not established\n
                                Please check connection and try again.""")
            
            self.h5_filepath = h5_filepath

            table = group['remote_device_operation'][:]
            
            for connection in table.dtype.names:
                value = float(table[0][connection]) # must cast `np.float32` to `float` to pass in JSON object
                response = self.remote_comms.program_value(connection, value)
                self.handle_response(response)

            # After buffered programming, get the values of all remote values before shot execution
            self.initial_monitor_values = self.check_all_remote_values()

            return {} # no buffered run final values to indicate

    def _save_monitor_values_to_hdf5(self, hdf5_file, group_name, monitor_values):
        if not monitor_values:
            return

        dtypes = [(name, np.float32) for name in monitor_values.keys()]
        static_value_table = np.zeros(1, dtype=dtypes)
        
        for connection, value in monitor_values.items():
            static_value_table[connection] = value

        try:
            group = hdf5_file[f'/data/{self.device_name}/monitor_values']
        except KeyError:
            group = hdf5_file.create_group(f'/data/{self.device_name}/monitor_values')
        
        group.create_dataset(f'{group_name}', data=static_value_table)
        
    def post_experiment(self):
        if self.initial_monitor_values:
            self.final_monitor_values = self.check_all_remote_values()
            # TODO: compare the buffered values with the current remote values at the end of the experiment.
            # if we have deviated too far, shot was unsuccessful and we need to requeue

            # Modify the connection names to be stored in the h5 and put into a single list
            with h5py.File(self.h5_filepath, 'a') as hdf5_file:
                self._save_monitor_values_to_hdf5(hdf5_file, 'initial_monitor_values', self.initial_monitor_values)
                self._save_monitor_values_to_hdf5(hdf5_file, 'final_monitor_values', self.final_monitor_values)

        self.initial_monitor_values = {}
        self.final_monitor_values = {}
        return True
    
    def transition_to_manual(self):
        return True

    def abort_transition_to_buffered(self):
        self.initial_monitor_values = {}
        self.final_monitor_values = {}
        return True

    def abort_buffered(self):
        self.initial_monitor_values = {}
        self.final_monitor_values = {}
        return True