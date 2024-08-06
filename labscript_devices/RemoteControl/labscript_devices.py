"""
NOTE:

This is the file that is used by labscript to COMPILE the instructions associated with this
device. This file has NOTHING to do with the operation with the actual device. 

The only interaction this file has with is defining the structure of the instructions the
BLACS workers will later consume. It also provides a way to set Connection table and device
properties for the worker functions to also use.
"""

"""
NOTE:

we should be making these RemoteControl devices PER NEW SOFTWARE WE WANT TO SUPPORT

- does it make sense to have some notion of base functionalities we extend from this class?
    - need to do some design thinking
"""
from labscript import(
    Device,
    StaticAnalogQuantity,
    set_passed_properties,
    LabscriptError,
    dedent
)
import numpy as np

class RemoteAnalogOut(StaticAnalogQuantity): # More appropriately named RemoteOutputValue
    description = "Remote Analog Output Value"
    
    @set_passed_properties(
        property_names={
            "connection_table_properties": [
                "units",
                "limits",
                "decimals",
                "step_size",
            ],
            "device_properties": [],
        }
    )
    def __init__(
        self, 
        name,
        parent_device,
        connection,
        units="V",
        limits=(0,np.inf),
        decimals=3,
        step_size=0.01,
        **kwargs
    ):
        """
        - the properties of the values you want to RECEIVE 
    Args:
            name (str): name to assign the created labscript device
            parent_device (str): The RemoteTab device this is connected to
            connection (str): this is the identifier of the value to be used by the remote program
            datatype (units, optional)
            limits (tuple, optional)
            decimals (int, optional)
        """
        # TODO: I think the limits should also be passed to the quantity
        # TODO: figure out what passing the limits actually control in the StaticAnalogQuantity initialization
        
        self._value_set = False

        StaticAnalogQuantity.__init__(
            self, 
            name, 
            parent_device, 
            connection, 
            limits=limits,
            **kwargs
        )
    
    def constant(self, value, units=None):
        self._value_set = True
        return super().constant(value, units=None)

    def value_set(self):
        return self._value_set

class RemoteAnalogMonitor(StaticAnalogQuantity): # More appropriately named RemoteMonitorValue
    description = "Remote Analog Monitor Value"
    @set_passed_properties(
        property_names={
            "connection_table_properties": [
                "units",
                "limits",
                "decimals",
                "step_size",
            ],
            "device_properties": [],
        }
    )
    def __init__(
        self,
        name,
        parent_device,
        connection, 
        units="V",
        limits=(0,np.inf),
        decimals=3, 
        step_size=0.01,
        **kwargs
    ):
        """
        - the properties of the values you want to RECEIVE 
        Args:
            name (str): name to assign the created labscript device
            parent_device (str): The RemoteTab device this is connected to
            connection (str): this is the identifier of the value to be used by the remote program
            datatype (units, optional)
            limits (tuple, optional)
            decimals (int, optional)
        """
        # TODO: I think the limits should also be passed to the quantity
        # TODO: figure out what passing the limits actually control in the StaticAnalogQuantity initialization
        StaticAnalogQuantity.__init__(
            self, 
            name, 
            parent_device, 
            connection,
            limits=limits,
            **kwargs
        )
"""
TODO:
add functionality to specify the bounds of the raster, for the raster specific device
    - should be recieved from remote a single time (NEED TO SET UP PUB/SUB)
"""
class RemoteControl(Device):
    # the RemoteControl should not require any children
    allowed_children = [RemoteAnalogOut, RemoteAnalogMonitor]
    
    description = 'Dummy Device for Remote Operation of Existing Software'

    @set_passed_properties(
        property_names={
            "connection_table_properties": [
                "host",
                "reqrep_port",
                "pubsub_port",
                "mock",
            ],
            "device_properties": [],
        }
    )
    def __init__(
        self, 
        name,
        host="",
        reqrep_port=None,
        pubsub_port=None,
        mock=True, 
        **kwargs
    ):
        """
        Generic class for remote operation of existing software

        Should be over-ridden by device-specific subclasses that contain the
        introspected default values.

        Args:
            name (str):
            host (str, optional): don't need to specify if in mock mode
            reqrep_port (int, optional) don't need to specify is in mock mode
            pubsub_port (int, optional) don't need to specify is in mock mode
            mock (bool, optional): 
        """
        # TODO: figure out why no other BLACS_connection works besides dummy_connection
        self.BLACS_connection = "dummy_connection"

        if (not mock) and (host=="" or (reqrep_port==None and pubsub_port==None)):
            raise Exception("Must specify the host and port of the remote software.")

        Device.__init__(self, name, None, None, **kwargs)

    def add_device(self, device):
        Device.add_device(self, device)
    
    def generate_code(self, hdf5_file):
        Device.generate_code(self, hdf5_file)
        analogs = {}
        # Only need to make table for the RemoteAnalogOut
        for device in self.child_devices:
            if isinstance(device, RemoteAnalogOut) and device.value_set():
                analogs[device.connection] = device
        if len(analogs.keys()) == 0:
            return
        connections = sorted(analogs)
        dtypes = [(connection, np.float32) for connection in connections]
        static_value_table = np.empty(1, dtype=dtypes)
        for connection, analog in analogs.items():
            static_value_table[connection][0] = analog.static_value
        grp = self.init_device_group(hdf5_file)
        grp.create_dataset('remote_device_operation', data=static_value_table)
