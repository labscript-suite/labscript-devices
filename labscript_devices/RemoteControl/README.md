# RemoteControl Device for Labscript

The **RemoteControl** device for labscript is designed to integrate pre-existing GUI applications used for controlling experimental apparatus. This integration removes the need to recreate complex GUIs within labscript, which can be time-consuming and complex. The RemoteControl device tab has three main features:

1. **RemoteAnalogOut**: Allows you to control analog outputs in your remote application.
2. **RemoteAnalogMonitor**: Continuously receive and update the BLACS tab to reflect remote values using a publish-subscribe architecture.
3. **EnableComms**: Toggles the ability to sending of analog outputs from BLACS to the remote application.

The RemoteControl device utilizes both synchronous and asynchronous communication methods. It uses ZeroMQ (ZMQ) REQ-REP sockets for synchronous communication to send commands (from labscript client) and receive responses (to remote device server), and PUB-SUB sockets for asynchronous updates of monitor values.

## Purpose and Functionality

In many cases, you may have a GUI application controlling parts of your experimental setup, such as programs for Rastering Laser Ablation or Locking Lasers. Using BLACS as your main experiment control application presents a challenge: BLACS cannot program/control devices that are not DeviceTabs.

For example, after defining your experiment shot logic, you may want to repeat the shot as you raster your ablation laser in a certain pattern or sweep your lasers over a range of frequencies. To achieve this, you need to communicate with and program the ablation laser or laser lock with the value for the next shot.

The **RemoteControl** device bridges this gap. By setting up the `RemoteControl` tab for your remote application (e.g., LaserRasterProgram) and defining the `RemoteAnalogOut`s you want to control along with the `RemoteAnalogMonitor`s you want to keep track of, you can easily write experimental logic to set values communicated over the network to the GUI software operating the device.

### Features

- **RemoteAnalogOut**: Set values to control parameters of the device in the remote GUI software.
- **RemoteAnalogMonitor**: Continuously read and update the BLACS tab to reflect remote values.
- **EnableComms**: Toggle communication between BLACS and the remote GUI.

### Operating Modes
To usage of the `RemoteControl` device is possibly best explained by listing its flow in all modes of BLACS operation. 

#### Manual Mode Flow
_Manual mode allows the user to provide manual control over devices when experiment shots are not running_
- **EnableComms=True**:
  - `RemoteAnalogMonitor` values are updated asynchronously via the PUB-SUB socket.
    - BLACS is updated as frequently as the remote device changes and publishes values.
  - `RemoteAnalogOut` values are checked at a slower polling rate (e.g., 0.1Hz) using the REQ-REP socket.
    - When communications are enabled, the user operates the BLACS tab to set these values. If a conflict arises (e.g., the user also adjusts the values through the remote GUI), a non-fatal GUI flag prompts the user to confirm whether to use the remote values or continue with the local setpoints. Since this scenario is uncommon (the user should not modify the remote GUI if BLACS is sending values), the check is performed at a slower rate.
  - If `RemoteAnalogOut` values are modified in BLACS, a network packet is sent to the remote GUI using the REQ-REP socket, and we wait for a success response indicating the device was moved to the specified value.
- **EnableComms=False**:
  - `RemoteAnalogMonitor` values continue to be updated asynchronously via the PUB-SUB socket.
  - `RemoteAnalogOut` values are checked at a faster polling rate (e.g., 2Hz) using the REQ-REP socket.
    - When communications are not enabled, no values are sent from BLACS, allowing the device to be operated freely from the remote GUI. We want to poll faster to stay as up-to-date on the remote values being set
  - `RemoteAnalogOut`s are disabled for manual entry, and values are updated to match the remote values based on the above polling.

#### State Machine (Executing h5 Shot File) Flow

- **EnableComms=True**:
  - Send compiled values to the remote device using the REQ-REP socket and wait for a success response.
  - At the start of a shot, read the initial `RemoteAnalogMonitor` values using the REQ-REP socket.
  - At the end of a shot, read the final `RemoteAnalogMonitor` values and verify their consistency.
    - Depending on the device, implement logic to ensure that the monitor values have not deviated significantly (e.g., verifying that the laser remained locked). If deviations are detected, handle the state machine flow appropriately to address issues such as the laser coming unlocked at the end of a shot.
  - Save these snapshots in the h5 file for analysis.

- **EnableComms=False**:
  - No values are programmed. However, at the beginning of the shot, read and save the remote GUI values of the `RemoteAnalogOut`s using the REQ-REP socket. This way, we know the value of all devices when the shot occured even if we didn't program their values.
  - Similarly, read and save the initial and final `RemoteAnalogMonitor` values using the REQ-REP socket.

## Setting Up RemoteControl

1. Identify values to control or monitor in your existing GUI application.
2. In your labscript connection_table/experiment script, define `RemoteAnalogOut` for read/write values and `RemoteAnalogMonitor` for read-only values.
    * Ensure the connection names specified for these objects match the ones you use in the remote GUI software. This is crucial to correctly identify and communicate with the correct values.
3. Set up both REQ-REP and PUB-SUB sockets in your remote GUI application to handle synchronous commands and asynchronous updates respectively.

### Labscript Example

```python
from user_devices.RemoteControl.labscript_devices import RemoteControl, RemoteAnalogOut, RemoteAnalogMonitor

RemoteControl(name='LaserRasterGUI', host='localhost', port=1234)
RemoteAnalogOut(name='laser_x_control', parent=remote_laser_raster_GUI, connection='laser_x_pos')
RemoteAnalogOut(name='laser_y_control', parent=remote_laser_raster_GUI, connection='laser_y_pos')
RemoteAnalogMonitor(name='laser_x_actual_value', parent=remote_laser_raster_GUI, connection='laser_x_actual_value')
RemoteAnalogMonitor(name='laser_y_actual_value', parent=remote_laser_raster_GUI, connection='laser_y_actual_value')

x_coord = RUNMANAGER_GLOBALS[RASTER_PATTERN_X_COORD]
y_coord = RUNMANAGER_GLOBALS[RASTER_PATTERN_Y_COORD]

laser_x_control.constant(x_coord)
laser_y_control.constant(y_coord)
```

* Note: connection `laser_x_pos` and `laser_y_pos` will be used as an identifier in the remote LaserRasterProgram to communicate with whatever code controls the devices x and y positions.
* In the example above, the `RemoteAnalogMonitor` for the raster program are not strictly necessary, as programming the motor to a setpoint will maintain that setpoint until modified. `RemoteAnalogMonitor` can either be omitted or connected to the same remote values as the `RemoteAnalogOut`.

### Communication Protocol
The `RemoteControl` device uses a JSON-based protocol for REQ-REP communication and simple string-based protocol for PUB-SUB communication:

#### Requests

```json
{
    "action": "<string>",
    "connection": "<string>",
    "value": "<any>"
}
```

* action: Operation to perform (one of "PROGRAM_VALUE", "CHECK_VALUE")
* connection: Identifier for the specific control or monitor
* value: Value to set (for "PROGRAM_VALUE" actions)

#### Responses

```json
{
    "status": "<string>",
    "message": "<string>",
    "value": "<any>"
}
```

* status: The status (one of "SUCCESS" or "ERROR")
* message: Error message (if applicable)
* value: Current value (for "CHECK_VALUE" actions)

#### PUB-SUB Messages

```
"{connection} {value}"
```

* connection: Identifier for the specific monitor (acts as the topic)
* value: Current value of the monitor

### Setting Up the Server in Your Existing GUI Application
To integrate your existing GUI application with the RemoteControl device:

1. Implement a ZeroMQ (ZMQ) REP socket to listen for incoming read/write requests.
2. Implement a ZeroMQ (ZMQ) PUB socket to send monitor updates.
3. Create a request handler to process JSON messages according to the protocol.
4. Implement a publisher to send monitor updates according to the PUB-SUB protocol 

#### Example Server Implementation

```python
import zmq
import json
import time
import threading
import random

context = zmq.Context()

# REQ-REP socket
rep_socket = context.socket(zmq.REP)
rep_socket.bind("tcp://*:1234")

# PUB-SUB socket
pub_socket = context.socket(zmq.PUB)
pub_socket.bind("tcp://*:1235")

def handle_request(request):
    try:
        data = json.loads(request)
        action = data['action']
        connection = data['connection']
        if action == 'PROGRAM_VALUE':
            setpoint_value = data['value']
            # TODO: Implement the code to set the value associated with the connection
            SET_VALUE(connection, setpoint_value)
            return json.dumps({"status": "SUCCESS"})
        elif action == 'CHECK_VALUE':
            current_value = GET_VALUE(connection)
            # TODO: Implement the code to get the current value associated with the connection
            return json.dumps({"status": "SUCCESS", "value": current_value})
        else:
            return json.dumps({"status": "ERROR", "message": "Invalid action"})
    except Exception as e:
        return json.dumps({"status": "ERROR", "message": str(e)})

def publish_monitor_updates():
    while True:
        # Simulating monitor updates
        laser_x = random.uniform(0, 10)
        laser_y = random.uniform(0, 10)
        
        pub_socket.send_string(f"laser_x_actual_value {laser_x}")
        pub_socket.send_string(f"laser_y_actual_value {laser_y}")
        
        time.sleep(0.1)  # Publish every 100ms

# Start the publisher thread
publisher_thread = threading.Thread(target=publish_monitor_updates, daemon=True)
publisher_thread.start()

# Main loop for handling REQ-REP communication
while True:
    request = rep_socket.recv().decode()
    response = handle_request(request)
    rep_socket.send(response.encode())
```