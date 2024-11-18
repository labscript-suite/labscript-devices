SignalGenerator
===============

Overview
--------

This is a parent class for static RF Signal Generators with frequency and amplitude control and
use the IEEE 488 or SCPI command protocols. Device communication is handled using the VISA
communication protocol.

.. autosummary::
	 naqslab_devices.SignalGenerator.Models
	 naqslab_devices.SignalGenerator.blacs_tab
	 naqslab_devices.SignalGenerator.blacs_worker
	 naqslab_devices.SignalGenerator.labscript_device
	 naqslab_devices.SignalGenerator.register_classes

Models
------

Currently covered models include:

.. currentmodule:: naqslab_devices.SignalGenerator.BLACS

.. autosummary::
	 HP_8642A
	 HP_8643A
	 HP_8648
    RS_SMA100B
	 RS_SMF100A
	 RS_SMHU
    KeysightSigGens

Adding a Signal Generator
-------------------------

In order to add a new model of signal generator one must:

#. Add a subclass :obj:`SignalGenerator.labscript_device` in :obj:`SignalGenerator.Models` 
   which provides the operational limits. 
#. Subclass :obj:`SignalGenerator.blacs_tab`
   and :obj:`SignalGenerator.blacs_worker` with the operational details for communicating
   with the device (namely command syntax and status byte definitions). 
#. Add an entry in :obj:`SignalGenerator.register_classes` that links the labscript_device to 
   the correct blacs_tab. Note that multiple labscript_devices can use the same blacs_tab/blacs_worker. 

Detailed Documentation
----------------------

.. automodule:: naqslab_devices.SignalGenerator.BLACS.HP_8642A
   :members:
   :undoc-members:
   :show-inheritance:


.. automodule:: naqslab_devices.SignalGenerator.BLACS.HP_8643A
   :members:
   :undoc-members:
   :show-inheritance:


.. automodule:: naqslab_devices.SignalGenerator.BLACS.HP_8648
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: naqslab_devices.SignalGenerator.BLACS.RS_SMA100B
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: naqslab_devices.SignalGenerator.BLACS.RS_SMF100A
   :members:
   :undoc-members:
   :show-inheritance:


.. automodule:: naqslab_devices.SignalGenerator.BLACS.RS_SMHU
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: naqslab_devices.SignalGenerator.BLACS.KeysightSigGens
   :members:
   :undoc-members:
   :show-inheritance:


.. automodule:: naqslab_devices.SignalGenerator.Models
   :members:
   :undoc-members:
   :show-inheritance:


.. automodule:: naqslab_devices.SignalGenerator.blacs_tab
   :members:
   :undoc-members:
   :show-inheritance:


.. automodule:: naqslab_devices.SignalGenerator.blacs_worker
   :members:
   :undoc-members:
   :show-inheritance:


.. automodule:: naqslab_devices.SignalGenerator.labscript_device
   :members:
   :undoc-members:
   :show-inheritance:


.. automodule:: naqslab_devices.SignalGenerator.register_classes
   :members:
   :undoc-members:
   :show-inheritance: