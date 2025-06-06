from labscript_devices import register_classes
import json
import os
from labscript_devices.BS_Series.logger_config import logger

THIS_FOLDER = os.path.dirname(os.path.abspath(__file__))
CAPABILITIES_FILE = os.path.join(THIS_FOLDER, 'models', 'capabilities.json')

capabilities = {}
if os.path.exists(CAPABILITIES_FILE):
    with open(CAPABILITIES_FILE) as f:
        capabilities = json.load(f)

register_classes(
    "BS_",
    BLACS_tab='labscript_devices.BS_Series.BLACS_tabs.BS_Tab',
    runviewer_parser=None,
)

for model_name in capabilities:
    logger.debug(f"Registering model: {model_name}")

    try:
        register_classes(
            model_name,
            BLACS_tab='labscript_devices.BS_Series.BLACS_tabs.BS_Tab',
            runviewer_parser=None,
        )
    except Exception as e:
        logger.error(f"Error registering {model_name}: {e}")