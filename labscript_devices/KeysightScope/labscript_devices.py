from labscript import TriggerableDevice, LabscriptError, set_passed_properties ,LabscriptError, AnalogIn

## ---------------------------------------------------------------New imports
from labscript_devices.KeysightScope.connection_manager import * 
from labscript_devices.KeysightScope.models.default_properties import default_osci_capabilities, default_osci_shot_configuration



class KeysightScope(TriggerableDevice):
    """
    Defines the interface between 
        the labscript API and generates hardware instructions that can be saved to the shot h5 file.
    A labscript_device for Keysight oscilloscopes (DSOX1202G) using a visa interface.
          - connection_table_properties (set once)
          - device_properties (set per shot)
    """

    @set_passed_properties(
        property_names = {
            'connection_table_properties': list(default_osci_capabilities.keys()),
            'device_properties': list(default_osci_shot_configuration.keys())
            }
        )
    def __init__(self, 
                 name, 
                 parent_device, 
                 connection,
                 serial_number,
                 **kwargs):
        TriggerableDevice.__init__(self, name, parent_device, connection, **kwargs) # parentless=False # connetion = "trigger"

        self.name = name

        cm = connectionManager(serial_number)
        self.BLACS_connection = cm.get_address_from_serial_number()
        osci_capabilities = cm.osci_capabilities
        osci_shot_configuration = cm.osci_shot_configuration

        set_passed_properties( 
            property_names = {
                'connection_table_properties' : list(osci_capabilities.keys()) ,
                "device_properties": list(osci_shot_configuration.keys())
                } 
            ) 
        
        # --------------------------------- Device properties
        for key,value in osci_capabilities.items():
            setattr(self,key,value)
        # --------------------------------- Shot configurations
        for key, value in osci_shot_configuration.items():
            setattr(self, key, value)

        # Device can only be triggered zero or one time
        self.triggered = False 


    def trigger_at(self, t, duration ):
        if self.triggered:
            raise LabscriptError("Cannot trigger Keysight Oscilloscope twice")
        self.triggered = True
        self.trigger(t, duration)


    def generate_code(self, hdf5_file, *args): 
        TriggerableDevice.generate_code(self, hdf5_file)
        
        





