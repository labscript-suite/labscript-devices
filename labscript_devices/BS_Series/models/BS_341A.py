from labscript_devices.BS_Series.labscript_devices import BS_
import json
import os

THIS_FOLDER = os.path.dirname(os.path.abspath(__file__))
CAPABILITIES_FILE = os.path.join(THIS_FOLDER, 'capabilities.json')
with open(CAPABILITIES_FILE, 'r') as f:
    CAPABILITIES = json.load(f).get('BS_341A', {})


class BS_341A(BS_):
    description = 'BS_341A'

    def __init__(self, *args, **kwargs):
        """Class for BS 34-1A basic configuration"""
        combined_kwargs = CAPABILITIES.copy()
        combined_kwargs.update(kwargs)
        BS_.__init__(self, *args, **combined_kwargs)