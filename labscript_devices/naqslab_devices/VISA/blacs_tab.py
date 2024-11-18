#####################################################################
#                                                                   #
# /naqslab_devices/VISA/blacs_tab.py                                #
#                                                                   #
# Copyright 2018, David Meyer                                       #
#                                                                   #
# This file is part of the naqslab devices extension to the         #
# labscript_suite. It is licensed under the Simplified BSD License. #
#                                                                   #
#                                                                   #
#####################################################################
"""
Boiler plate blacs_tab for VISA instruments. 

Defines the common STBstatus.ui widget all devices use to report their current status.
"""
from labscript import LabscriptError
     
from blacs.tab_base_classes import define_state
from blacs.tab_base_classes import MODE_MANUAL, MODE_TRANSITION_TO_BUFFERED, MODE_TRANSITION_TO_MANUAL, MODE_BUFFERED  
from blacs.device_base_class import DeviceTab
from qtutils import UiLoader
import os

# Imports for handling icons in STBstatus.ui
from qtutils.qt import QtCore
from qtutils.qt import QtGui

class VISATab(DeviceTab):
    # Define the Status Byte labels with this dictionary structure
    status_byte_labels = {'bit 7':'bit 7 label', 
                          'bit 6':'bit 6 label',
                          'bit 5':'bit 5 label',
                          'bit 4':'bit 4 label',
                          'bit 3':'bit 3 label',
                          'bit 2':'bit 2 label',
                          'bit 1':'bit 1 label',
                          'bit 0':'bit 0 label'}
    status_widget = 'STBstatus.ui'
    
    STBui_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),status_widget)
    
    def __init__(self,*args,**kwargs):
        """You MUST override this method in order to define the device worker.
        You then call this parent method to finish initialization.
        """
        if not hasattr(self,'device_worker_class'):
            raise LabscriptError('BLACS worker not set for device: {0:s}'.format(self))
        DeviceTab.__init__(self,*args,**kwargs)
    
    def initialise_GUI(self):
        """Loads the standard STBstatus.ui widget and sets the worker defined in __init__"""
        # load the status_ui for the STB register
        self.status_ui = UiLoader().load(self.STBui_path)
        self.get_tab_layout().addWidget(self.status_ui)
                   
        # generate the dictionaries
        self.status_bits = ['bit 0', 'bit 1', 'bit 2', 'bit 3', 'bit 4', 'bit 5', 'bit 6', 'bit 7']
        self.bit_labels_widgets = {}
        self.bit_values_widgets = {}
        self.status = {}
        for bit in self.status_bits:
            self.status[bit] = False
            self.bit_values_widgets[bit] = getattr(self.status_ui, 'status_{0:s}'.format(bit.split()[1]))
            self.bit_labels_widgets[bit] = getattr(self.status_ui, 'status_label_{0:s}'.format(bit.split()[1]))
        
        # Dynamically update status bits with correct names           
        for key in self.status_bits:
            self.bit_labels_widgets[key].setText(self.status_byte_labels[key])
        self.status_ui.clear_button.clicked.connect(self.send_clear)
        
        
        # Store the VISA name to be used
        self.address = str(self.settings['connection_table'].find_by_name(self.settings["device_name"]).BLACS_connection)
        #self.device_name = str(self.settings['device_name'])
        
        # Create and set the primary worker
        self.create_worker("main_worker",
                            self.device_worker_class,
                            {'address':self.address,
                            })
        self.primary_worker = "main_worker"       

    
    # This function gets the status,
    # and updates the front panel widgets!
    @define_state(MODE_MANUAL|MODE_BUFFERED|MODE_TRANSITION_TO_BUFFERED|MODE_TRANSITION_TO_MANUAL,True)  
    def status_monitor(self):
        # When called with a queue, this function writes to the queue
        # when the pulseblaster is waiting. This indicates the end of
        # an experimental run.
        self.status = yield(self.queue_work(self._primary_worker,'check_status'))

        for key in self.status_bits:
            if self.status[key]:
                icon = QtGui.QIcon(':/qtutils/fugue/tick')
            else:
                icon = QtGui.QIcon(':/qtutils/fugue/cross')
            pixmap = icon.pixmap(QtCore.QSize(16,16))
            self.bit_values_widgets[key].setPixmap(pixmap)
        
        
    @define_state(MODE_MANUAL|MODE_BUFFERED|MODE_TRANSITION_TO_BUFFERED|MODE_TRANSITION_TO_MANUAL,True,True)
    def send_clear(self,widget=None):
        value = self.status_ui.clear_button.isChecked()
        yield(self.queue_work(self._primary_worker,'clear',value))

