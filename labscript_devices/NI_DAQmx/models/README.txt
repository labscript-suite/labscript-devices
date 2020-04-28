Warning: capabilities.json, register_classes.py and files named NI_<model_name>.py in
this folder are auto-generated. If you modify them, your modifications may be
overwritten.

To add support for a DAQmx device that is not yet supported, run get_capabilities.py on
a computer with the device in question connected (or with a simulated device of the
correct model configured in NI-MAX). This will introspect the capabilities of the device
and add those details to capabilities.json. To generate labscript device classes for all
devices whose capabilities are known, run generate_classes.py. Subclasses of NI_DAQmx
will be made in this folder, and they can then be imported into labscript code with:

from labscript_devices.NI_DAQmx.labscript_devices import NI_PCIe_6363

or similar. The class naming is based on the model name by prepending "NI_" and
replacing the hyphen with an underscore, i.e. 'PCIe-6363' -> NI_PCIe_6363.

Generating device classes requires the Python code-formatting library 'black', which can
be installed via pip (Python 3.6+ only). If you don't want to install this library, the
generation code will still work, it just won't be formatted well.
