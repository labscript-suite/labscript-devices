import os
import json
from labscript_devices import import_class_by_fullname

THIS_FOLDER = os.path.dirname(os.path.abspath(__file__))
CAPABILITIES_FILE = os.path.join(THIS_FOLDER, 'capabilities.json')

capabilities = {}
if os.path.exists(CAPABILITIES_FILE):
    with open(CAPABILITIES_FILE) as f:
        capabilities = json.load(f)

__all__ = []
# Import all subclasses into the global namespace:
for model_name in capabilities:
    class_name = model_name
    path = f'labscript_devices.BS_Series.models.{model_name}.{class_name}'
    globals()[class_name] = import_class_by_fullname(path)
    __all__.append(class_name)