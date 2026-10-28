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
"""Deprecated import locations for names that are defined in the submodules of a device
package."""
import importlib
import sys
import warnings


def deprecated_names(package, locations):
    """Return a module ``__getattr__`` function for the package with the fully qualified
    name ``package``. ``locations`` is a dict that maps the name of each submodule of the
    package to a list of names that are defined in that submodule. Getting one of these
    names as an attribute of the package, including with ``from package import name``,
    returns the object from the submodule. The first time that each name is accessed,
    this issues a ``FutureWarning`` that gives the submodule and sets the name as an
    attribute of the package."""
    submodules = {name: submodule for submodule, names in locations.items() for name in names}

    def __getattr__(name):
        try:
            submodule = submodules[name]
        except KeyError:
            msg = f"module {package!r} has no attribute {name!r}"
            raise AttributeError(msg) from None
        fullname = f'{package}.{submodule}'
        msg = f"Importing {name} from {package} is deprecated. Import it from {fullname}."
        warnings.warn(msg, FutureWarning, stacklevel=2)
        value = getattr(importlib.import_module(fullname), name)
        setattr(sys.modules[package], name, value)
        return value

    return __getattr__
