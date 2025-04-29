from labscript import TriggerableDevice, LabscriptError, set_passed_properties ,LabscriptError,set_passed_properties
import  h5py

# ---------------------------------------------------------------New imports
from labscript_devices.KeysightScope.connection_manager import * 


default_osci_capabilities = [    # Example:  Keysight DSOX1202G
        "serial_number"   ,      # Serial number Must be given when initializing the Oscilloscope
        "band_width"      ,      # 70 MHz
        "sampling_rate"   ,      # 2GSa/s
        "max_memory"      ,      # 1Mpts
        "max_update_rate"        # 50,000 waveforms/second update rate.   

]

class KeysightScope(TriggerableDevice):
    """
    A labscript_device for Keysight oscilloscopes (1200 X-Series and EDUX1052A/G) using a visa interface.
          - connection_table_properties (set once)
          - device_properties (set per shot)
    """

    @set_passed_properties(
        property_names = {
            'connection_table_properties':  default_osci_capabilities,
            'device_properties' : ["configuration_number","triggered", "timeout"]
            }
        )
    def __init__(self, 
                 name, 
                 parent_device, 
                 serial_number,
                 connection = "trigger",
                 timeout = 10,
                 **kwargs):
        TriggerableDevice.__init__(self, name, parent_device, connection, **kwargs) 

        # --------------------------------- Connection Manager
        cm = connectionManager(serial_number)
        self.BLACS_connection = cm.get_address_from_serial_number()

        # --------------------------------- Device capabilities
        self.osci_capabilities = cm.osci_capabilities
        for key,value in self.osci_capabilities.items():
            setattr(self,key,value)

        # --------------------------------- Class attributes
        self.name = name
        self.triggered = False              # Device can only be triggered Zero or one time
        self.configuration_number = None    # Sets the configuraton slot
        self.timeout = timeout

        
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


    def trigger_at(self, t, duration ):
        if self.triggered:
            raise LabscriptError("Cannot trigger Keysight Oscilloscope twice")
        self.triggered = True
        self.trigger(t, duration)


    def generate_code(self, hdf5_file, *args):                  
        TriggerableDevice.generate_code(self, hdf5_file)

        if self.configuration_number is not None:
            self.set_property('configuration_number', self.configuration_number, location='device_properties', overwrite=True)

        if self.triggered:
            self.set_property('triggered', self.triggered , location='device_properties', overwrite=True)







