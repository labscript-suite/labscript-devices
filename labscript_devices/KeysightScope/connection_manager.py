import os
import importlib
import pyvisa
from re import sub

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

class connectionManager:
    def __init__(self, serial_number=None, address = None, folder_name="models"):

        self.serial_number = serial_number
        self.address = address
        self.folder_name = folder_name 

        # List of the supported Keysight oscilloscopes
        self.supported_models = ["EDUX1052A", "EDUX1052G", "DSOX1202A", "DSOX1202G", "DSOX1204A", "DSOX1204G"]
        
        # ----------------------------- Pyvisa ressources
        self.rm = pyvisa.ResourceManager()
        self.devs = self.rm.list_resources()

        # ----------------------------- serial_number initialization
        if self.serial_number is not None:
            self.current_file = self.pick_file_from_serial_number()         # Dictionary containing all the module attributes

            if self.current_file is None:
                raise ValueError(f"File with serial number {self.serial_number} not found.")
        
            self.osci_shot_configuration = self.current_file["osci_shot_configuration"]
            self.osci_capabilities = self.current_file["osci_capabilities"]


        # ----------------------------- Address initialization
        if self.address is not None:    
            self.current_file = self.pick_file_from_adress()                # Dictionary containing all the module attributes

            if self.current_file is None:
                raise ValueError(f"File with serial number {self.serial_number} not found.")
            
            self.osci_shot_configuration = self.current_file["osci_shot_configuration"]
            self.osci_capabilities = self.current_file["osci_capabilities"]

    
    def _get_files_from_folder(self):
        """ 
        Retrieves all files from the specified folder (default is "models"). 
        The folder is assumed to be part of the KeysightScope directory structure.
        
        Returns:
            list: A list of file names in the specified folder.

        Raises:
            FileNotFoundError: If the specified folder does not exist.
        """
        file_path = os.path.abspath(__file__)                                   # Absolute path of this file
        containing_folder = os.path.dirname(file_path)                          # Absolute path of the containing folder
        keysight_scope_dir = os.path.join(containing_folder, self.folder_name)  # Absolute path to the desired folder (default is "models")

        # Check if the directory exists
        if not os.path.exists(keysight_scope_dir):
            raise FileNotFoundError(f"The folder '{self.folder_name}' does not exist in the KeysightScope directory.")
        
        # Get all files in the folder
        #files = [f for f in os.listdir(keysight_scope_dir) if os.path.isfile(os.path.join(keysight_scope_dir, f))]
        files = [os.path.abspath(os.path.join(keysight_scope_dir, f)) for f in os.listdir(keysight_scope_dir) if os.path.isfile(os.path.join(keysight_scope_dir, f))]
        return files
    
    def pick_file_from_serial_number(self, serial_number = None):
        """ 
        Selects the first file that contains the serial number in its name.
        
        Returns:
            file: The initialization file that corresponds to the serial number, or None if no file is found.
        """
        if serial_number is None:
            serial_number = self.serial_number

        files = self._get_files_from_folder()

        for file_path in files:
            with open(file_path, 'r') as f:  # Open the file in read mode
                content = f.read()
                if serial_number in content:
                    module_name = os.path.basename(file_path)[:-3]
                    spec = importlib.util.spec_from_file_location(module_name, file_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module) 

                    # Create a dictionary to store the module's attributes
                    module_attributes = {}

                    # Iterate over all attributes of the module
                    for attribute_name in dir(module):
                        if not attribute_name.startswith('__'):
                            # Get the attribute value
                            attribute_value = getattr(module, attribute_name)

                            # Store the attribute and its value in the dictionary
                            module_attributes[attribute_name] = attribute_value

                    #Return the dictionary of attributes
                    return module_attributes

        return None



############################################################################
#                               Done                                       #
############################################################################

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

  
        isRightModel = False
        isRightSerialNumber = False

        for idx, item in enumerate(self.devs):
            try:
                scope = self.rm.open_resource(self.devs[idx], timeout=500)          # opens the device
                osci_model = scope.query("*IDN?")                                   # asks about the identity
                
                for supported_model in self.supported_models:                       # checks if it is a supported model
                    if supported_model in osci_model:
                        isRightModel = True

                # Check the serial number 
                scope_serial_number = sub(r'\s+', '', scope.query(":SERial?"))      # gets the device serial number
                isRightSerialNumber = (scope_serial_number == serial_number)   # checks the conformity between the given and the read serial number

                if isRightSerialNumber and isRightModel:                            
                    return item
                elif not isRightModel and isRightSerialNumber:
                    raise ValueError(f"The device model {osci_model} is not supported. Supported models are EDUX1052A, EDUX1052G, DSOX1202A, DSOX1202G, DSOX1204A, DSOX1204G.")
            except:
                continue

        if not isRightSerialNumber:
            raise ValueError(f"No Device with the serial number {serial_number} was found.")
                
    def pick_file_from_adress(self):
        scope = self.rm.open_resource(self.address, timeout=500)
        scope_serial_number = sub(r'\s+', '', scope.query(":SERial?"))
        return self.pick_file_from_serial_number(scope_serial_number)



# ------------------------------------------------------------------------ Testing
if __name__ == "__main__":
    cm = connectionManager(serial_number="CN61364200")
    print(cm.osci_capabilities)


