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

    status_byte_labels = {'bit 7':'Powered On', 
                          'bit 6':'Button Pressed',
                          'bit 5':'Command Error',
                          'bit 4':'Execution Error',
                          'bit 3':'Device Error',
                          'bit 2':'Query Error',
                          'bit 1':'Unused',
                          'bit 0':'Operation Complete'}
    
    status_widget = 'STBstatus.ui'
    STBui_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),status_widget)

    def initialise_workers(self):
        # Here we can change can initialisation properties in the connection table
        worker_initialisation_kwargs = self.connection_table.find_by_name(self.device_name).properties

        # Note that adding porperties as follows allows the blacs worker to access them
        # This comes in handy for the device initialisation
        worker_initialisation_kwargs['address'] = self.BLACS_connection     # important to get the right connection in blacs


        # Create the device worker
        self.create_worker(
            'main_worker',
            'labscript_devices.KeysightScope.blacs_workers.KeysightScopeWorker',
            worker_initialisation_kwargs,
        )
        self.primary_worker = 'main_worker'


    def initialise_GUI(self):
        self.status_ui = UiLoader().load(self.STBui_path)
        self.get_tab_layout().addWidget(self.status_ui)
        
        # Get capabilities from connection table properties:
        # reminder connection_table is an instance of ConnectionTable
        #properties = self.connection_table.find_by_name(self.device_name).properties


        # create a GUI based on these properties 
        # generate the dictionaries
        self.status_bits = ['bit 0', 'bit 1', 'bit 2', 'bit 3', 'bit 4', 'bit 5', 'bit 6', 'bit 7']
        self.bit_labels_widgets = {}
        self.bit_values_widgets = {}
        self.status = {}
        for bit in self.status_bits:
            self.status[bit] = False
            self.bit_values_widgets[bit] = getattr(self.status_ui, 'status_{0:s}'.format(bit.split()[1]))
            self.bit_labels_widgets[bit] = getattr(self.status_ui, 'status_label_{0:s}'.format(bit.split()[1]))

        for key in self.status_bits:
            self.bit_labels_widgets[key].setText(self.status_byte_labels[key])
        self.status_ui.clear_button.clicked.connect(self.test_func)
        
        return

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

    
    @define_state(MODE_MANUAL|MODE_BUFFERED|MODE_TRANSITION_TO_BUFFERED|MODE_TRANSITION_TO_MANUAL,True,True)
    def test_func(self,widget=None):
        value = self.status_ui.clear_button.isChecked()
        yield(self.queue_work(self._primary_worker,'clear',value))