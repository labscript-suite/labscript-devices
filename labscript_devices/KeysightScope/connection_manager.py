import os
import importlib.util
import pyvisa
from re import sub

if __name__ =="__main__":
    import models
else : 
    import labscript_devices.KeysightScope.models as models


def get_address_from_description(description):
    # List to store the imported dictionaries
    osci_shot_configuration = []
    osci_capabilities = []

    # List of decives detected by pyvisa
    rm = pyvisa.ResourceManager()
    devs = rm.list_resources()

    # Loop through all modules in the models package
    for filename in os.listdir(models.__path__[0]):
        # Check if the file starts with "Keysight" and is a .py file
        if filename.startswith("Keysight") and filename.endswith(".py"):
            # Construct the module name (without the .py extension)
            module_name = filename[:-3]
            
            # Dynamically import the module from the models package
            if __name__ =="__main__":
                module = importlib.import_module(f"models.{module_name}")
            else : module = importlib.import_module(f"labscript_devices.KeysightScope.models.{module_name}")
            
            # Try to access the dictionaries if they exist in the module
            if hasattr(module, 'osci_shot_configuration'):
                osci_shot_configuration = module.osci_shot_configuration
            
            if hasattr(module, 'osci_capabilities'):
                osci_capabilities = module.osci_capabilities

            if description == osci_shot_configuration["description"]:
                for idx, item in enumerate(devs):
                    try:
                        scope = rm.open_resource(devs[idx], timeout=200)
                        scope_serial_number = sub(r'\s+', '', scope.query(":SERial?")) 
                        if scope_serial_number == osci_capabilities['serial_number']:
                            return item
                    except:
                        continue


def get_configuration_from_description(description):
    # List to store the imported dictionaries
    osci_shot_configuration = []
    osci_capabilities = []
    # Loop through all modules in the models package
    for filename in os.listdir(models.__path__[0]):
        # Check if the file starts with "Keysight" and is a .py file
        if filename.startswith("Keysight") and filename.endswith(".py"):
            # Construct the module name (without the .py extension)
            module_name = filename[:-3]
            
            # Dynamically import the module from the models package
            if __name__ =="__main__":
                module = importlib.import_module(f"models.{module_name}")
            else : module = importlib.import_module(f"labscript_devices.KeysightScope.models.{module_name}")
            
            # Try to access the dictionaries if they exist in the module
            if hasattr(module, 'osci_shot_configuration'):
                osci_shot_configuration = module.osci_shot_configuration
            
            if hasattr(module, 'osci_capabilities'):
                osci_capabilities = module.osci_capabilities

            if description == osci_shot_configuration["description"]:
                return osci_shot_configuration

  
def get_capabilities_from_description(description):
    # Loop through all modules in the models package
    for filename in os.listdir(models.__path__[0]):
        # Check if the file starts with "Keysight" and is a .py file
        if filename.startswith("Keysight") and filename.endswith(".py"):
            # Construct the module name (without the .py extension)
            module_name = filename[:-3]
            
            # Dynamically import the module from the models package
            if __name__ =="__main__":
                module = importlib.import_module(f"models.{module_name}")
            else : module = importlib.import_module(f"labscript_devices.KeysightScope.models.{module_name}")
            
            # Try to access the dictionaries if they exist in the module
            if hasattr(module, 'osci_shot_configuration'):
                osci_shot_configuration = module.osci_shot_configuration
            
            if hasattr(module, 'osci_capabilities'):
                osci_capabilities = module.osci_capabilities

            if description == osci_shot_configuration["description"]:
                return osci_capabilities





# ----------------------------------- tests
if __name__ == "__main__":

    # # get_address_from_description
    # adrr = get_address_from_description('Example Osci')
    # rm = pyvisa.ResourceManager()
    # devs = rm.list_resources()
    # scope = rm.open_resource(adrr)
    # print(scope.query("*IDN?"))

    print(get_capabilities_from_description('Example Osci'))
    print(get_configuration_from_description('Example Osci'))

