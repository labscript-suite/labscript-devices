#####################################################################
#                                                                   #
# /labscript_devices/common/deprecation.py                          #
#                                                                   #
# Copyright 2026, Christopher Billington                            #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
"""Deprecated import locations for names that are defined in other modules."""
import importlib
import sys
import warnings


def deprecated_names(module, locations):
    """Return a module ``__getattr__`` function for the module with the fully qualified
    name ``module``. ``locations`` is a dict that maps module names to lists of names
    that are defined in those modules. A module name is either the name of a submodule
    of ``module``, or a fully qualified name if it contains a dot. Getting one of the
    names as an attribute of ``module``, including with ``from module import name``,
    returns the object from the module that defines it. The first time that each name is
    accessed, this issues a ``FutureWarning`` that gives that module, and sets the name
    as an attribute of ``module``."""
    sources = {}
    for source, names in locations.items():
        if '.' not in source:
            source = f'{module}.{source}'
        for name in names:
            sources[name] = source

    def __getattr__(name):
        try:
            source = sources[name]
        except KeyError:
            msg = f"module {module!r} has no attribute {name!r}"
            raise AttributeError(msg) from None
        msg = f"Importing {name} from {module} is deprecated. Import it from {source}."
        warnings.warn(msg, FutureWarning, stacklevel=2)
        value = getattr(importlib.import_module(source), name)
        setattr(sys.modules[module], name, value)
        return value

    return __getattr__
