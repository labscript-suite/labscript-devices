
import os
import sys
import importlib
import imp
import warnings
import traceback
import inspect
from labscript_utils import dedent
from labscript_utils.labconfig import LabConfig

from .__version__ import __version__


"""This file contains the machinery for registering and looking up what BLACS tab and
runviewer parser classes belong to a particular labscript device. "labscript device"
here means a device that BLACS needs to communicate with. These devices have
instructions saved within the 'devices' group of the HDF5 file, and have a tab
corresponding to them in the BLACS interface. These device classes must have unique
names, such as "PineBlaster" or "PulseBlaster" etc.

There are two methods we use to find out which BLACS tab and runviewer parser correspond
to a device class: the "old" method, and the "new" method. The old method requires that
the the BLACS tab and runviewer parser be in a file called <DeviceName>.py at the top
level of labscript_devices folder, and that they have class decorators @BLACS_tab or
@runviewer_parser to identify them. This method precludes putting code in subfolders or
splitting it across multiple files.

The "new" method is more flexible. It allows BLACS tabs and runviewer parsers to be
defined in any importable file within a subfolder of labscript_devices. Additionally,
the 'user_devices' configuration setting in labconfig can be used to specify a
comma-delimited list of names of importable packages containing additional labscript
devices.

Classes using the new method can be in files with any name, and do not need class
decorators. Instead, the classes should be registered by creating a file called
'register_classes.py', which when imported, makes calls to
labscript_devices.register_classes() to register which BLACS tab and runviewer parser
class belong to each device. Tab and parser classes must be passed to register_classes()
as fully qualified names, i.e. "labscript_devices.submodule.ClassName", not by passing
in the classes themselves. This ensures imports can be deferred until the classes are
actually needed. When BLACS and runviewer look up classes with get_BLACS_tab() and
get_runviewer_parser(), populate_registry() will be called in order to find all files
called 'register_classes.py' within subfolders (at any depth) of labscript_devices, and
they will be imported to run their code and hence register their classes.

The "new" method does not impose any restrictions on code organisation within subfolders
of labscript_devices, and so is preferable as it allows auxiliary utilities or resource
files to live in subfolders alongside the device code to which they are relevant, the
use of subrepositories, the grouping of similar devices within subfolders, and other
nice things to have.

The old method may be deprecated in the future.
"""


def _get_import_paths(import_names):
    """For the given list of packages, return all folders containing their submodules.
    If the packages do not exist, ignore them."""
    paths = []
    for name in import_names:
        spec = importlib.util.find_spec(name)
        if spec is not None and spec.submodule_search_locations is not None:
            paths.extend(spec.submodule_search_locations)
    return paths


def _get_device_dirs():
    """Return the directory of labscript_devices, and the folders containing
    submodules of any packages listed in the user_devices labconfig setting"""
    try:
        user_devices = LabConfig().get('DEFAULT', 'user_devices')
    except (LabConfig.NoOptionError, LabConfig.NoSectionError):
        user_devices = 'user_devices'
    # Split on commas, remove whitespace:
    user_devices = [s.strip() for s in user_devices.split(',')]
    return _get_import_paths(['labscript_devices'] + user_devices)


LABSCRIPT_DEVICES_DIRS = _get_device_dirs()


class ClassRegister(object):
    """A register for looking up classes by module name.  Provides a
     decorator and a method for looking up classes decorated with it,
     importing as necessary."""
    def __init__(self, instancename):
        self.registered_classes = {}
        # The name given to the instance in this namespace, so we can use it in error messages:
        self.instancename = instancename

    def __call__(self, cls):
        """Adds the class to the register so that it can be looked up later
        by module name"""
        # Add an attribute to the class so it knows its own name in case
        # it needs to look up other classes in the same module:
        cls.labscript_device_class_name = cls.__module__.split('.')[-1]
        if cls.labscript_device_class_name == '__main__':
            # User is running the module as __main__. Use the filename instead:
            import __main__
            try:
                cls.labscript_device_class_name = os.path.splitext(os.path.basename(__main__.__file__))[0]
            except AttributeError:
                # Maybe they're running interactively? Or some other funky environment. Either way, we can't proceed.
                raise RuntimeError('Can\'t figure out what the file or module this class is being defined in. ' +
                                   'If you are testing, please test from a more standard environment, such as ' +
                                   'executing a script from the command line, or if you are using an interactive session, ' +
                                   'writing your code in a separate module and importing it.')

        # Add it to the register:
        self.registered_classes[cls.labscript_device_class_name] = cls
        return cls

    def __getitem__(self, name):
        try:
            # Ensure the module's code has run (this does not re-import it if it is already in sys.modules)
            importlib.import_module('.' + name, __name__)
        except ImportError:
            msg = """No %s registered for a device named %s. Ensure that there is a file
                'register_classes.py' with a call to
                labscript_devices.register_classes() for this device, with the device
                name passed to register_classes() matching the name of the device class.

                Fallback method of looking for and importing a module in
                labscript_devices with the same name as the device also failed. If using
                this method, check that the module exists, has the same name as the
                device class, and can be imported with no errors. Import error
                was:\n\n"""
            msg = dedent(msg) % (self.instancename, name) + traceback.format_exc()
            raise ImportError(msg)
        # Class definitions in that module have executed now, check to see if class is in our register:
        try:
            return self.registered_classes[name]
        except KeyError:
            # No? No such class is defined then, or maybe the user forgot to decorate it.
            raise ValueError('No class decorated as a %s found in module %s, '%(self.instancename, __name__ + '.' + name) +
                             'Did you forget to decorate the class definition with @%s?'%(self.instancename))


# Decorating labscript device classes and BLACS worker classes was never used for
# anything and has been deprecated. These decorators can be removed with no ill
# effects. Do nothing, and emit a warning telling the user this.
def deprecated_decorator(name):
    def null_decorator(cls):
        msg = '@%s decorator is unnecessary and can be removed' % name
        warnings.warn(msg, stacklevel=2)
        return cls

    return null_decorator


labscript_device = deprecated_decorator('labscript_device')
BLACS_worker = deprecated_decorator('BLACS_worker')


# These decorators can still be used, but their use will be deprecated in the future
# once all devices in mainline are moved into subfolders with a register_classes.py that
# will play the same role. For the moment we support both mechanisms of registering
# which BLACS tab and runviewer parser class belong to a particular device.
BLACS_tab = ClassRegister('BLACS_tab')
runviewer_parser = ClassRegister('runviewer_parser')


def import_class_by_fullname(fullname):
    """Import and return a class defined by its fully qualified name as an absolute
    import path, i.e. "module.submodule.ClassName"."""
    split = fullname.split('.')
    module_name = '.'.join(split[:-1])
    class_name = split[-1]
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def deprecated_import_alias(fullname):
    """A way of allowing a class to be imported from an old location whilst a) not
    actually importing it until it is instantiated and b) emitting a warning pointing to
    the new import location. fullname must be a fully qualified class name with an
    absolute import path. Use by calling in the module where the class used to be:
    ClassName = deprecated_import_alias("new.path.to.ClassName")"""
    calling_module_name = inspect.getmodule(inspect.stack()[1][0]).__name__
    cls = []
    def wrapper(*args, **kwargs):
        if not cls:
            cls.append(import_class_by_fullname(fullname))
            shortname = fullname.split('.')[-1]
            newmodule = '.'.join(fullname.split('.')[:-1])
            msg = """Importing %s from %s is deprecated, please instead import it from
               %s. Importing anyway for backward compatibility, but this may cause some
               unexpected behaviour."""
            msg = dedent(msg) % (shortname, calling_module_name, newmodule)
            warnings.warn(msg, stacklevel=2)
        return cls[0](*args, **kwargs)
    return wrapper


# Dictionaries containing the import paths to BLACS tab and runviewer parser classes,
# not the classes themselves. These will be populated by calls to register_classes from
# code within register_classes.py files within subfolders of labscript_devices.
BLACS_tab_registry = {}
runviewer_parser_registry = {}
# The script files that registered each device, for use in error messages:
_register_classes_script_files = {}

# Wrapper functions to get devices out of the class registries.
def get_BLACS_tab(name):
    if not BLACS_tab_registry:
        populate_registry()
    if name in BLACS_tab_registry:
        return import_class_by_fullname(BLACS_tab_registry[name])
    # Fall back on file naming convention + decorator method:
    return BLACS_tab[name]


def get_runviewer_parser(name):
    if not runviewer_parser_registry:
        populate_registry()
    if name in runviewer_parser_registry:
        return import_class_by_fullname(runviewer_parser_registry[name])
    # Fall back on file naming convention + decorator method:
    return runviewer_parser[name]


def register_classes(labscript_device_name, BLACS_tab=None, runviewer_parser=None):
    """Register the name of the BLACS tab and/or runviewer parser that belong to a
    particular labscript device. labscript_device_name should be a string of just the
    device name, i.e. "DeviceName". BLACS_tab_fullname and runviewer_parser_fullname
    should be strings containing the fully qualified import paths for the BLACS tab and
    runviewer parser classes, such as "labscript_devices.DeviceName.DeviceTab" and
    "labscript_devices.DeviceName.DeviceParser". These need not be in the same module as
    the device class as in this example, but should be within labscript_devices. This
    function should be called from a file called "register_classes.py" within a
    subfolder of labscript_devices. When BLACS or runviewer start up, they will call
    populate_registry(), which will find and run all such files to populate the class
    registries prior to looking up the classes they need"""
    if labscript_device_name in _register_classes_script_files:
        other_script =_register_classes_script_files[labscript_device_name]
        msg = """A device named %s has already been registered by the script %s.
            Labscript devices must have unique names."""
        raise ValueError(dedent(msg) % (labscript_device_name, other_script))
    BLACS_tab_registry[labscript_device_name] = BLACS_tab
    runviewer_parser_registry[labscript_device_name] = runviewer_parser
    script_filename = os.path.abspath(inspect.stack()[1][0].f_code.co_filename)
    _register_classes_script_files[labscript_device_name] = script_filename


def populate_registry():
    """Walk the labscript_devices folder looking for files called register_classes.py,
    and run them (i.e. import them). These files are expected to make calls to
    register_classes() to inform us of what BLACS tabs and runviewer classes correspond
    to their labscript device classes."""
    # We import the register_classes modules as a direct submodule of labscript_devices.
    # But they cannot all have the same name, so we import them as
    # labscript_devices._register_classes_script_<num> with increasing number.
    module_num = 0
    for devices_dir in LABSCRIPT_DEVICES_DIRS:
        for folder, _, filenames in os.walk(devices_dir):
            if 'register_classes.py' in filenames:
                # The module name is the path to the file, relative to the labscript suite
                # install directory:
                # Open the file using the import machinery, and import it as module_name.
                fp, pathname, desc = imp.find_module('register_classes', [folder])
                module_name = 'labscript_devices._register_classes_%d' % module_num
                _ = imp.load_module(module_name, fp, pathname, desc)
                module_num += 1


if __name__ == '__main__':
    # If this module is run as __main__, make sure importing submodules still works,
    # without double-importing this file:
    __path__ = [os.path.dirname(os.path.abspath(__file__))]
    sys.modules['labscript_devices'] = sys.modules['__main__']
