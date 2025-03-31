import os
import importlib
import pyvisa
from re import sub



class connectionManager:
    """ 
    This class manages the connection and initialization of supported Keysight oscilloscopes 
    using serial number or address for identifying and loading configuration files from the specified folder.
    """

    def __init__(self, 
                 serial_number=None, 
                 address = None, 
                 folder_name="models"
                 ):

        # ----------------------------- Init
        self.serial_number = serial_number
        self.address = address
        self.folder_name = folder_name 

        # ----------------------------- List of the supported Keysight oscilloscopes
        self.supported_models = ["EDUX1052A", "EDUX1052G", "DSOX1202A", "DSOX1202G", "DSOX1204A", "DSOX1204G"]
        
        # ----------------------------- Pyvisa ressources
        self.rm = pyvisa.ResourceManager()
        self.devs = self.rm.list_resources()

        # ----------------------------- Serial_number initialization
        if self.serial_number is None:
            raise ValueError("Serial number must be provided")
        else:
            self.current_file = self.pick_file_from_serial_number()         # Dictionary containing all the module attributes

            if self.current_file is None:
                raise ValueError(f"File with serial number {self.serial_number} not found.")
        
            self.osci_capabilities = self.current_file["osci_capabilities"]



    def _get_files_from_folder(self):
        """ Retrieves a list of all file paths in the specified folder (default is 'models') and returns their absolute paths. """
        file_path = os.path.abspath(__file__)                                   # Absolute path of this file
        containing_folder = os.path.dirname(file_path)                          # Absolute path of the containing folder
        keysight_scope_dir = os.path.join(containing_folder, self.folder_name)  # Absolute path to the desired folder (default is "models")

        # Check if the directory exists
        if not os.path.exists(keysight_scope_dir):
            raise FileNotFoundError(f"The folder '{self.folder_name}' does not exist in the KeysightScope directory.")
        
        # Get all file paths in the folder
        files = [os.path.abspath(os.path.join(keysight_scope_dir, f)) for f in os.listdir(keysight_scope_dir) if os.path.isfile(os.path.join(keysight_scope_dir, f))]
        return files
    
    def pick_file_from_serial_number(self, serial_number = None):
        """ 
        Searches for a configuration file based on the provided serial number (or the object's serial number if not provided).
        Loads the module and extracts its attributes, returning them as a dictionary.
        Returns None if no file with the given serial number is found.
        """
        if serial_number is None:
            serial_number = self.serial_number

        files = self._get_files_from_folder()

        for file_path in files:
            with open(file_path, 'r') as f:  
                content = f.read()
                if serial_number in content:
                    module_name = os.path.basename(file_path)[:-3]
                    spec = importlib.util.spec_from_file_location(module_name, file_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module) 

                    module_attributes = {}
                    for attribute_name in dir(module):
                        if not attribute_name.startswith('__'):
                            attribute_value = getattr(module, attribute_name)
                            module_attributes[attribute_name] = attribute_value

                    return module_attributes

        return None

    def get_address_from_serial_number(self, serial_number = None): 
        """
        Identifies to the oscilloscope with the given serial number and supported model.

        Iterates through the available devices, checks if their model and serial number match the expected ones,
        and returns the correct connection resource string for the oscilloscope.

        Returns:
            str: The connection resource string for the oscilloscope.

        Raises:
            ValueError: If no oscilloscope with the matching serial number or model is found.
        """
        if serial_number is None:
            serial_number = self.serial_number

        is_right_model= False
        is_right_serial_number = False

        for idx, item in enumerate(self.devs):
            try:
                scope = self.rm.open_resource(self.devs[idx], timeout=500)          # opens the device
                osci_model = scope.query("*IDN?")                                   # asks about the identity
                
                for supported_model in self.supported_models:                       # checks if it is a supported model
                    if supported_model in osci_model:
                        is_right_model= True

                # Check the serial number 
                scope_serial_number = sub(r'\s+', '', scope.query(":SERial?"))      # gets the device serial number
                is_right_serial_number = (scope_serial_number == serial_number)   # checks the conformity between the given and the read serial number

                if is_right_serial_number and is_right_model:                            
                    return item
                elif not is_right_model and is_right_serial_number:
                    raise ValueError(f"The device model {osci_model} is not supported. Supported models are EDUX1052A, EDUX1052G, DSOX1202A, DSOX1202G, DSOX1204A, DSOX1204G.")
            except:
                continue

        if not is_right_serial_number:
            raise ValueError(f"No Device with the serial number {serial_number} was found.")
                

# ----------------------------------- Miscellaneous

BLUE = '#66D9EF'
PURPLE = '#AE81FF'
GREEN = '#A6E22E'
GREY = '#75715E' 

unit_conversion = {
            's' : 1  ,  
            'ns': 1e-9,  # nanoseconds to seconds
            'us': 1e-6,  # microseconds to seconds
            'ms': 1e-3   # milliseconds to seconds
            }
# ----------------------------------- Miscellaneous


# ------------------------------------------------------------------------ Testing
if __name__ == "__main__":
    cm = connectionManager(serial_number="CN61364200")
    print(cm.osci_capabilities)


