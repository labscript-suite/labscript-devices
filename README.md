<img src="https://raw.githubusercontent.com/labscript-suite/labscript-suite/master/art/labscript_32nx32n.svg" height="64" alt="the labscript suite" align="right">

# the _labscript suite_ » labscript-devices

### Plugin architecture for controlling experiment hardware

[![Actions Status](https://github.com/labscript-suite/labscript-devices/workflows/Build%20and%20Release/badge.svg?branch=maintenance%2F3.0.x)](https://github.com/labscript-suite/labscript-devices/actions)
[![License](https://img.shields.io/pypi/l/labscript-devices.svg)](https://github.com/labscript-suite/labscript-devices/raw/master/LICENSE.txt)
[![Python Version](https://img.shields.io/pypi/pyversions/labscript-devices.svg)](https://python.org)
[![PyPI](https://img.shields.io/pypi/v/labscript-devices.svg)](https://pypi.org/project/labscript-devices)
[![Conda Version](https://img.shields.io/conda/v/labscript-suite/labscript-devices)](https://anaconda.org/labscript-suite/labscript-devices)
[![Google Group](https://img.shields.io/badge/Google%20Group-labscriptsuite-blue.svg)](https://groups.google.com/forum/#!forum/labscriptsuite)
<!-- [![DOI](http://img.shields.io/badge/DOI-10.1063%2F1.4817213-0F79D0.svg)](https://doi.org/10.1063/1.4817213) -->


A modular and extensible plugin architecture to control experiment hardware using the [*labscript suite*](https://github.com/labscript-suite/labscript-suite).

The *labscript suite* supports a range of commercial and open-source hardware, and is modular by design. Adding support for new devices involves writing Python functions for a well-defined set of primitives to program instructions, and transition between buffered I/O and manual states. See the [documentation](http://labscriptsuite.org/documentation) for more details on adding new devices.


## Supported hardware

The following devices have been implemented in the _labscript suite_:<sup>†</sup>
* [AlazarTech](https://www.alazartech.com) PCI Express Digitizers (e.g. [ATS9462](https://www.alazartech.com/Product/ATS9462); PR [#41](http://bitbucket-archive.labscriptsuite.org/#!/labscript_suite/labscript_devices/pull-requests/41))
* [LightCrafter DMD](http://www.ti.com/tool/DLPLCR4500EVM) Digital Micro-mirror Device (PR [#43](https://bitbucket-archive.labscriptsuite.org/#!/labscript_suite/labscript_devices/pull-requests/43))
* [MOGLabs Agile RF Synthesizers](https://www.moglabs.com/products/rf-electronics/agile-rf-synth) (ARF/XRF)
* [National Instruments Data Acquisition](http://www.ni.com/data-acquisition/) ([DAQmx](https://knowledge.ni.com/KnowledgeArticleDetails?id=kA00Z000000P8baSAC)) devices:
  * [cDAQ-9184](https://www.ni.com/en-us/support/model.cdaq-9184.html) CompactDAQ Chassis
  * [PCI 6251](https://www.ni.com/en-au/support/model.pci-6251.html) Multifunction I/O Device
  * [PCI 6533/6534](http://www.ni.com/pdf/manuals/371464d.pdf) High-Speed Digital Pattern I/O
  * [PCI-6713](https://www.ni.com/en-au/support/model.pci-6713.html) Analog Output Device
  * [PCI-6733](https://www.ni.com/en-au/support/model.pci-6733.html) Analog Output Device
  * PCI-DIO-32HS High-Speed Digital I/O
  * [PCIe-6363](https://www.ni.com/en-us/support/model.pcie-6363.html) Multifunction I/O Device
  * [PCIe-6738](https://www.ni.com/en-us/support/model.pcie-6738.html) Analog Output Device
  * [PXI-6733](https://www.ni.com/en-au/support/model.pxi-6733.html) PXI Analog Output Module
  * [PXIe-6361](https://www.ni.com/en-au/support/model.pxie-6361.html) PXI Multifunction I/O Module
  * [PXIe-6535](https://www.ni.com/en-ie/support/model.pxie-6535.html) PXI Digital I/O Module
  * [PXIe-6738](https://www.ni.com/en-au/support/model.pxie-6738.html) PXI Analog Output Module
  * [USB-6008](https://www.ni.com/en-au/support/model.usb-6008.html) Multifunction I/O Device
  * [USB-6229](https://www.ni.com/en-my/support/model.usb-6229.html) Multifunction I/O Device
  * [USB-6343](https://www.ni.com/en-us/support/model.usb-6343.html) Multifunction I/O Device
  * [Quicksyn FSW-0010](http://ni-microwavecomponents.com/quicksyn-full) Microwave Synthesizer (formerly PhaseMatrix)
  
  **Note:** Since v2.5.0 (June 2019), [`labscript_devices.NI_DAQmx`](https://github.com/labscript-suite/labscript-devices/tree/master/labscript_devices/NI_DAQmx) can be used to automatically generate a labscript device class for _any_ NI-DAQmx device! (PR [#56](https://bitbucket-archive.labscriptsuite.org/#!/labscript_suite/labscript_devices/pull-requests/56))

* [NovaTech DDS9m](http://www.novatechsales.com/PDF_files/dds9mds_lr.pdf) 170MHz Four Channel Direct Digital Synthesized Signal Generator (see [blog post](http://labscriptsuite.org/blog/tag/novatech-dds9m/))
* [OpalKelly XEM3001](https://opalkelly.com/products/xem3001/) FPGA Boards used by the Cicero control system (PR [#50](https://bitbucket-archive.labscriptsuite.org/#!/labscript_suite/labscript_devices/pull-requests/50))
* [PineBlaster](http://labscriptsuite.org/hardware/pineblaster) Open-source Digital Pattern Generator
* [SpinCore](https://www.spincore.com/products/#pulsegeneration) Programmable Pulse Generators and Direct Digital Synthesis
  * [PulseBlasterDDS-II-300-AWG](http://www.spincore.com/products/PulseBlasterDDS-II-300/)
  * [PulseBlasterESR-PRO](https://www.spincore.com/products/PulseBlasterESR-PRO/)
  * [PulseBlasterESR-CompactPCI](https://www.spincore.com/products/PulseBlasterESR-CompactPCI/)
  * [PulseBlaster](https://www.spincore.com/products/PulseBlaster/) e.g. SP2 Model: PB24-100-32k
  * [PulseBlasterUSB](https://www.spincore.com/products/PulseBlasterUSB/)
* [Tektronix oscilloscopes](https://www.tek.com/oscilloscope) (PR [#61](https://bitbucket-archive.labscriptsuite.org/#!/labscript_suite/labscript_devices/pull-requests/56))
* [Zaber](https://www.zaber.com) Motion Controllers, e.g. linear translation stages (PR [#85](https://bitbucket-archive.labscriptsuite.org/#!/labscript_suite/labscript_devices/pull-requests/85))


### Supported cameras

The following cameras are implemented by subclassing [`labscript_devices.Camera`](https://github.com/labscript-suite/labscript-devices/tree/master/labscript_devices/Camera.py), a Python-based camera server which can be controlled directly from [**blacs**](https://github.com/labscript-suite/blacs).

* [FLIR](https://www.flir.com) cameras (e.g. [FlyCapture 2](https://github.com/labscript-suite/labscript-devices/tree/master/labscript_devices/FlyCapture2Camera)) using the free PyCapture2 API (PR [#71](https://bitbucket-archive.labscriptsuite.org/#!/labscript_suite/labscript_devices/pull-requests/9))
* [Andor](https://github.com/labscript-suite/labscript-devices/tree/master/labscript_devices/AndorSolis) cameras (PR [#80](https://github.com/labscript-suite/labscript-devices/tree/master/labscript_devices/AndorSolis))
* [Basler pylon](https://github.com/labscript-suite/labscript-devices/tree/master/labscript_devices/PylonCamera) (PRs [#69](https://bitbucket-archive.labscriptsuite.org/#!/labscript_suite/labscript_devices/pull-requests/69) and [#74](https://bitbucket-archive.labscriptsuite.org/#!/labscript_suite/labscript_devices/pull-requests/74)).
* Any camera compatible with National Instruments [IMAQdx](https://github.com/labscript-suite/labscript-devices/tree/master/labscript_devices/IMAQdxCamera) (PRs [#70](https://bitbucket-archive.labscriptsuite.org/#!/labscript_suite/labscript_devices/pull-requests/70), [#72](https://bitbucket-archive.labscriptsuite.org/#!/labscript_suite/labscript_devices/pull-requests/72), [#73](https://bitbucket-archive.labscriptsuite.org/#!/labscript_suite/labscript_devices/pull-requests/73), [#77](https://bitbucket-archive.labscriptsuite.org/#!/labscript_suite/labscript_devices/pull-requests/77), [#79](https://bitbucket-archive.labscriptsuite.org/#!/labscript_suite/labscript_devices/pull-requests/79), [#83](https://bitbucket-archive.labscriptsuite.org/#!/labscript_suite/labscript_devices/pull-requests/83)).
* This includes most cameras compliant with the [GigE Vision](https://en.wikipedia.org/wiki/GigE_Vision) interface standard, such as [Allied Vision](https://www.alliedvision.com/en/products/cameras.html) cameras.

† We do not endorse the use of any particular hardware.


## Installation

labscript-devices is distributed as a Python package on [PyPI](https://pypi.org/user/labscript-suite) and [Anaconda Cloud](https://anaconda.org/labscript-suite), and should be installed with other components of the _labscript suite_. Please see the [installation guide](https://docs.labscriptsuite.org/en/latest/installation) for details.
