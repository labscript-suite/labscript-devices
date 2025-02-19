from labscript import TriggerableDevice, LabscriptError, set_passed_properties ,LabscriptError, AnalogIn
#from labscript_devices.KeysightScope.models.Keysight_dsox1202g import osci_capabilities, osci_shot_configuration
from labscript_devices.KeysightScope.connection_manager import * 


# -------------------- Change me 
description = "Example Osci"
# ------------------------------

adress = get_address_from_description(description)
osci_capabilities = get_capabilities_from_description(description)
osci_shot_configuration = get_configuration_from_description(description)
connection_table_properties = list(osci_capabilities.keys()) 
device_properties = list(osci_shot_configuration.keys())


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
            'device_properties': device_properties
            }
        )
    def __init__(self, 
                 name, 
                 parent_device, 
                 description, 
                 **kwargs):
        TriggerableDevice.__init__(self, name, parent_device, "trigger", **kwargs) # parentless=False
        self.name = name
        self.description = description
        self.BLACS_connection = get_address_from_description(self.description)

        osci_capabilities = get_capabilities_from_description(self.description)
        osci_shot_configuration = get_configuration_from_description(self.description)
        #set_passed_properties(property_names={"device_properties": list(osci_shot_configuration.keys())})(self) # maybe this way 
        
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
        
        
# Another Methode for adding prop   
"""
    Another way
    # 1 in class KeysightScope(TriggerableDevice): we passed the args with the init values 
            init 
                acquisation_rate=10e6,
                max_amplitude = 5,
                v_div = 2,
                t_div=1e-3,

    # 2 of cource then  
                self.acquisation_rate = acquisation_rate
                self.max_amplitude = max_amplitude
                self.t_div = t_div
                self.v_div = v_div

            oder so
                def set_parameters(self, 
                       acquisation_rate=None, 
                       max_amplitude=None, 
                       t_div=None, 
                       v_div=None):

                if acquisation_rate is not None:
                    self.acquisation_rate = acquisation_rate
                if max_amplitude is not None:
                    self.max_amplitude = max_amplitude
                if v_div is not None:
                    self.v_div = v_div
                if t_div is not None:
                    self.t_div = t_div

        # Last in generate code 
            group = self.init_device_group(hdf5_file)

                # Setup device properties
                group.attrs["triggered"] = self.triggered
                group.attrs["acquisation_rate"] = self.acquisation_rate

                # trigger types
                group.attrs["max_amplitude"] =  self.max_amplitude
                group.attrs["t_div"] = self.t_div
                group.attrs["v_div"] = self.v_div

"""


            







