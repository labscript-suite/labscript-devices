# from blacs.device_base_class import DeviceTab

# from labscript import LabscriptError
     
# from blacs.tab_base_classes import define_state
# from blacs.tab_base_classes import MODE_MANUAL, MODE_TRANSITION_TO_BUFFERED, MODE_TRANSITION_TO_MANUAL, MODE_BUFFERED  
# from blacs.device_base_class import DeviceTab
# from qtutils import UiLoader
# import os
# # Imports for handling icons in STBstatus.ui
# from qtutils.qt import QtCore
# from qtutils.qt import QtGui

# class KeysightScopeTab(DeviceTab):
#     def initialise_GUI(self):
#         print("Hello World")

#     def initialise_workers(self):
#         worker_initialisation_kwargs = self.connection_table.find_by_name(self.device_name).properties
#         worker_initialisation_kwargs['addr'] = self.BLACS_connection # vermutung : remote
#         self.create_worker(
#             'main_worker',
#             'labscript_devices.KeysightScope.blacs_workers.KeysightScopeWorker',
#             worker_initialisation_kwargs,
#         )
#         self.primary_worker = 'main_worker'

####################################################################### NEW 

from blacs.device_base_class import DeviceTab

from labscript import LabscriptError
     
from blacs.tab_base_classes import define_state,Worker
from blacs.tab_base_classes import MODE_MANUAL, MODE_TRANSITION_TO_BUFFERED, MODE_TRANSITION_TO_MANUAL, MODE_BUFFERED  
from blacs.device_base_class import DeviceTab
from qtutils import UiLoader
# from PyQt5.QtWidgets import QPushButton
import os


from qtutils.qt import QtCore
from qtutils.qt import QtGui


"""
The Device class: handles the creation of the GUI + interaction GUI ~ QueueManager

    These are run in order : 
        - self.initialise_GUI()
        - self.restore_save_data(settings_dictionary)
        - self.initialise_workers()
"""
class KeysightScopeTab(DeviceTab): 
    def initialise_GUI(self):
        
        # Get capabilities from connection table properties:
        connection_table = self.settings['connection_table']
        properties = connection_table.find_by_name(self.device_name).properties
        # create a GUI based on these properties 
        return

        
    def initialise_workers(self):
        worker_initialisation_kwargs = self.connection_table.find_by_name(self.device_name).properties
        worker_initialisation_kwargs['addr'] = self.BLACS_connection 
        self.create_worker(
            'main_worker',
            'labscript_devices.KeysightScope.blacs_workers.KeysightScopeWorker',
            worker_initialisation_kwargs,
        )
        self.primary_worker = 'main_worker'
