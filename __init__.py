import os
import sys
import importlib

__version__ = '2.0.2'

from labscript_utils import check_version

check_version('labscript_utils', '2.2', '3')
check_version('labscript', '2.1', '3')
check_version('blacs', '2.1', '3')


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
            print 'imported', name, 'ok!'
        except ImportError:
            sys.stderr.write('Error importing module %s.%s whilst looking for classes for device %s. '%(__name__, name, name) +
                             'Check that the module exists, is named correctly, and can be imported with no errors. ' +
                             'Full traceback follows:\n')
            raise
        # Class definitions in that module have executed now, check to see if class is in our register:
        try:
            return self.registered_classes[name]
        except KeyError:
            # No? No such class is defined then, or maybe the user forgot to decorate it.
            raise ValueError('No class decorated as a %s found in module %s, '%(self.instancename, __name__ + '.' + name) +
                             'Did you forget to decorate the class definition with @%s?'%(self.instancename))

class SameNameClassRegister(ClassRegister):
    """Subclass of ClassRegister that also checks that the
    class has the same name as the file it is in."""
    def __call__(self, cls):
        ClassRegister.__call__(self, cls)
        if cls.labscript_device_class_name != cls.__name__:
            raise ValueError('The class decorated as a @labscript_device must have the same name as the file it is in. ' +
                             'For example NI_PCI_6733.py: class NI_PCI_6733(IntermediateDevice). ' +
                             'Otherwise labscript suite programs looking for it won\'t know what file to look in!')
        return cls

# The decorators the user should apply to their classes so that the
# respective programs can look them up:
labscript_device = SameNameClassRegister('labscript_device')
BLACS_tab = ClassRegister('BLACS_tab')
BLACS_worker = ClassRegister('BLACS_worker')
runviewer_parser = ClassRegister('runviewer_parser')

# Wrapper functions to get devices out of the class registers.
def get_labscript_device(name):
    return labscript_device[name]

def get_BLACS_tab(name):
    return BLACS_tab[name]

def get_BLACS_worker(name):
    return BLACS_worker[name]

def get_runviewer_parser(name):
    return runviewer_parser[name]


