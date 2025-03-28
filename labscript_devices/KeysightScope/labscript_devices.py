from labscript import TriggerableDevice, LabscriptError, set_passed_properties ,LabscriptError,set_passed_properties

# ---------------------------------------------------------------New imports
from labscript_devices.KeysightScope.connection_manager import * 
from labscript_devices.KeysightScope.models.default_properties import default_osci_capabilities, default_osci_shot_configuration



class KeysightScope(TriggerableDevice):
    """
    A labscript_device for Keysight oscilloscopes (1200 X-Series and EDUX1052A/G) using a visa interface.
          - connection_table_properties (set once)
          - device_properties (set per shot)
    """

    @set_passed_properties(
        property_names = {
            'connection_table_properties':  list(default_osci_capabilities.keys()) ,
            'device_properties' : ["configuration_number"]
            }
        )
    def __init__(self, 
                 name, 
                 parent_device, 
                 serial_number,
                 connection = "trigger",
                 **kwargs):
        TriggerableDevice.__init__(self, name, parent_device, connection, **kwargs) 

        self.name = name

        cm = connectionManager(serial_number)
        self.BLACS_connection = cm.get_address_from_serial_number()

        self.triggered = False              # Device can only be triggered zero or one time
        self.configuration_number = None    # Sets the configuraton slot

        # --------------------------------- Device properties
        self.osci_capabilities = cm.osci_capabilities
        for key,value in self.osci_capabilities.items():
            setattr(self,key,value)

        

    def set_config(self,configuration_number):
        """
        Change the configuration of the oscilloscope to the specified configuration number.

        Args:
            configuration_number (str or int): The number of the configuration to switch to (0-9).
            
        Raises:
            LabscriptError: If the configuration number is not between 0 and 9.
        """
        if not (0 <= configuration_number <= 9):
            raise LabscriptError("Value must be between 0 and 9")
        
        self.configuration_number = configuration_number
        #setattr(self,'configuration_number', configuration_number)

    

    def trigger_at(self, t, duration ):
        if self.triggered:
            raise LabscriptError("Cannot trigger Keysight Oscilloscope twice")
        self.triggered = True
        self.trigger(t, duration)


    def generate_code(self, hdf5_file, *args): 
        TriggerableDevice.generate_code(self, hdf5_file)

        hdf5_file[f'/devices/{self.name}'].attrs["configuration_number"] = self.configuration_number


        
        





