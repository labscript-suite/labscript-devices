<img src="https://raw.githubusercontent.com/labscript-suite/labscript-suite/master/art/labscript_32nx32n.svg" height="64" alt="the labscript suite" align="right">

# the _labscript suite_ » labscript-devices

### Plugin architecture for controlling experiment hardware

[![Actions Status](https://github.com/labscript-suite/labscript-devices/workflows/Build%20and%20Release/badge.svg)](https://github.com/labscript-suite/labscript-devices/actions)
[![License](https://img.shields.io/pypi/l/labscript-devices.svg)](https://github.com/labscript-suite/labscript-devices/raw/master/LICENSE.txt)
[![Python Version](https://img.shields.io/pypi/pyversions/labscript-devices.svg)](https://python.org)
[![PyPI](https://img.shields.io/pypi/v/labscript-devices.svg)](https://pypi.org/project/labscript-devices)
[![Conda Version](https://img.shields.io/conda/v/labscript-suite/labscript-devices)](https://anaconda.org/labscript-suite/labscript-devices)
[![Google Group](https://img.shields.io/badge/Google%20Group-labscriptsuite-blue.svg)](https://groups.google.com/forum/#!forum/labscriptsuite)
<!-- [![DOI](http://img.shields.io/badge/DOI-10.1063%2F1.4817213-0F79D0.svg)](https://doi.org/10.1063/1.4817213) -->


A modular and extensible plugin architecture to control experiment hardware using the [*labscript suite*](https://github.com/labscript-suite/labscript-suite).

The *labscript suite* supports a range of commercial and open-source hardware, and is modular by design. Adding support for new devices involves writing Python functions for a well-defined set of primitives to program instructions, and transition between buffered I/O and manual states. See the [documentation](https://docs.labscriptsuite.org/projects/labscript-devices/en/latest/user_devices/) for more details on adding new devices.


## Supported hardware

The [device list](https://docs.labscriptsuite.org/projects/labscript-devices/en/latest/devices/) in the documentation lists the devices that labscript-devices supports.


## Installation

labscript-devices is distributed as a Python package on [PyPI](https://pypi.org/user/labscript-suite) and [Anaconda Cloud](https://anaconda.org/labscript-suite), and should be installed with other components of the _labscript suite_. Please see the [installation guide](https://docs.labscriptsuite.org/en/latest/installation) for details.
