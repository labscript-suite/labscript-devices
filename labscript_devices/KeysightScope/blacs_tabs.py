from blacs.device_base_class import DeviceTab
from labscript import LabscriptError    
from blacs.tab_base_classes import define_state,Worker
from blacs.tab_base_classes import MODE_MANUAL, MODE_TRANSITION_TO_BUFFERED, MODE_TRANSITION_TO_MANUAL, MODE_BUFFERED  
from blacs.device_base_class import DeviceTab

import os
import sys
from PyQt5.QtWidgets import * 
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PyQt5.QtCore import QSize
from PyQt5 import uic

"""
The device class handles the creation of the GUI + interaction GUI ~ QueueManager

"""

class KeysightScopeTab(DeviceTab): 

    def initialise_workers(self):
        # Here we can change the initialization properties in the connection table
        worker_initialisation_kwargs = self.connection_table.find_by_name(self.device_name).properties

        # Adding porperties as follows allows the blacs worker to access them
        # This comes in handy for the device initialization
        worker_initialisation_kwargs['address'] = self.BLACS_connection   

        # Create the device worker
        self.create_worker(
            'main_worker',
            'labscript_devices.KeysightScope.blacs_workers.KeysightScopeWorker',
            worker_initialisation_kwargs,
        )
        self.primary_worker = 'main_worker'


    def initialise_GUI(self):

        # The Osci Widget
        self.osci_widget = OsciTab()
        self.get_tab_layout().addWidget(self.osci_widget)
        
        # Connect radio buttons (activate slot)
        for i in range(10):
            self.radio_button = self.osci_widget.findChild(QRadioButton, f"activeRadioButton_{i}")
            self.radio_button.clicked.connect(lambda checked, i=i: self.activate_radio_button(i))

            # Connect load buttons (load current)
            self.load_button = self.osci_widget.findChild(QPushButton, f"loadButton_{i}")
            self.load_button.clicked.connect(lambda clicked, i=i: self.load_current_config(i))

            # Connect load buttons slot (load slot)
            self.load_button = self.osci_widget.findChild(QPushButton, f"loadButtonSlot_{i}")
            self.load_button.clicked.connect(lambda clicked, i=i: self.load_slot_config(i))

            # connect reset buttons (default buttons)
            self.default_button = self.osci_widget.findChild(QPushButton, f"defaultButton_{i}")
            self.default_button.clicked.connect(lambda clicked, i=i: self.default_config(i))

        # Loads the Osci Configurations
        self.init_osci()

        return

    @define_state(MODE_MANUAL|MODE_BUFFERED|MODE_TRANSITION_TO_BUFFERED|MODE_TRANSITION_TO_MANUAL,True,True)
    def init_osci(self,widget=None ):
        list_dict_config = yield(self.queue_work(self._primary_worker,'init_osci'))

        for key,value in list_dict_config.items():
            if value:
                self.osci_widget.load_parameters(current_dict=value , table_index= key)
            else:
                self.default_config( button_id=key)
                
    @define_state(MODE_MANUAL|MODE_BUFFERED|MODE_TRANSITION_TO_BUFFERED|MODE_TRANSITION_TO_MANUAL,True,True)
    def activate_radio_button(self,buttton_id, widget=None ):
        yield(self.queue_work(self._primary_worker,'activate_radio_button',buttton_id))

    @define_state(MODE_MANUAL|MODE_BUFFERED|MODE_TRANSITION_TO_BUFFERED|MODE_TRANSITION_TO_MANUAL,True,True)
    def load_current_config(self,button_id, widget=None ):
        dict_config = yield(self.queue_work(self._primary_worker,'load_current_config',button_id))
        self.osci_widget.load_parameters(current_dict=dict_config , table_index= button_id)

    # @define_state(MODE_MANUAL|MODE_BUFFERED|MODE_TRANSITION_TO_BUFFERED|MODE_TRANSITION_TO_MANUAL,True,True)
    # def load_slot_config(self,button_id, widget=None ):
    #     dict_config = yield(self.queue_work(self._primary_worker,'load_slot_config',button_id))
    #     self.osci_widget.load_parameters(current_dict=dict_config , table_index= button_id)

    @define_state(MODE_MANUAL|MODE_BUFFERED|MODE_TRANSITION_TO_BUFFERED|MODE_TRANSITION_TO_MANUAL,True,True)
    def default_config(self,button_id, widget=None ):
        dict_config = yield(self.queue_work(self._primary_worker,'default_config',button_id))
        self.osci_widget.load_parameters(current_dict=dict_config , table_index= button_id)


class TabTemplate(QWidget):
    """ A Tab template class that defines the oscilloscope configuration in a table format,
    designed to describe the most important settings for the ten available storage slots of the oscilloscope."""
    def __init__(self,parent=None):
        super().__init__(parent)
        tab_template_name = 'tab_template.ui'
        tab_template_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),tab_template_name)
        uic.loadUi(tab_template_path,self) 


class OsciTab(QWidget):
    """ The oscilloscope Widget """
    def __init__(self, parent=None):
        super().__init__(parent) 

        tabs_name = 'tabs.ui'
        tabs_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),tabs_name)
        uic.loadUi(tabs_path,self) 
        
        # --- Children
        self.tabWidget = self.findChild(QTabWidget,"tabWidget")
        self.previous_checked_index = None
        
        self.label_active_setup = self.findChild(QLabel,"label_active_setup")
        self.button_group = QButtonGroup(self)

        # yes_icon = self.style().standardIcon(QStyle.SP_DialogApplyButton)  
        reset_icon = self.style().standardIcon(QStyle.SP_BrowserReload) 
        load_icon = self.style().standardIcon(QStyle.SP_DialogOpenButton)
        
        for i in range(self.tabWidget.count()):
            
            # --- Promote Tabs
            self.tabWidget.removeTab(i)
            self.tabWidget.insertTab(i, TabTemplate(), f"s{i}")          # Add the new widget to the layout
            tab = self.tabWidget.widget(i) 
            
            # --- RadioButtons
            radio_button = tab.findChild(QRadioButton, "activeRadioButton")
            radio_button.setObjectName(f"activeRadioButton_{i}")
            self.button_group.addButton(radio_button)
            self.button_group.setId(radio_button, i  )
            radio_button.toggled.connect(self.radio_toggled )

            # --- ToolButtons
            self.load_button = tab.findChild(QPushButton , "loadButton")
            self.load_button.setObjectName(f"loadButton_{i}")
            self.load_button.setIcon(load_icon)
            self.load_button.setIconSize(QSize(16,16))

            # self.load_button_slot = tab.findChild(QPushButton , "loadButtonSlot")
            # self.load_button_slot.setObjectName(f"loadButtonSlot_{i}")
            # self.load_button_slot.setIcon(load_icon)
            # self.load_button.setIconSize(QSize(16,16))
            
            self.default_button = tab.findChild(QPushButton , "defaultButton")
            self.default_button.setObjectName(f"defaultButton_{i}")
            self.default_button.setIcon(reset_icon)
            self.default_button.setIconSize(QSize(16,16))
            
            # --- TableWidgets
            self.tableWidget = tab.findChild(QTableWidget, "tableWidget")
            self.tableWidget.setObjectName(f"table_{i}")
            self.tableWidget.setRowCount(30)
            self.tableWidget.setColumnCount(2)
            self.tableWidget.setHorizontalHeaderLabels(["Parameter", "Value"])
            self.tableWidget.setEditTriggers(QTableWidget.NoEditTriggers)  
            header = self.tableWidget.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.Stretch)  # Stretch all columns to fill the space
                
       # --- Style Sheet 
        self.sh_tab = """
            QTabBar::tab {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                            stop:0 #ffffff, stop:1 #dddddd);
                border: 1px solid #aaa;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 10px 20px;
                color: #333;
                font-weight: bold;
            }
        """
        self.sh_selected_tab = """
            QTabBar::tab:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                            stop:0 #7BD77B, stop:1 #68C068);
                color: white;
                border-bottom: 2px solid #339933;
            }
        """    
        self.tabWidget.setStyleSheet(self.sh_tab + self.sh_selected_tab)

        # --- init 
        self.button_group.button(0).setChecked(True)
        self.tabWidget.setCurrentIndex(0)
        
    # --- Connecting the radio buttons 
    def radio_toggled (self):
        selected_button = self.sender()
        
        if self.previous_checked_index is not None:
            self.tabWidget.setTabText(self.previous_checked_index, f"s{self.previous_checked_index}" )
            
        if selected_button.isChecked():
            index = self.button_group.id(selected_button) 
            self.label_active_setup.setText("Active setup : " + self.tabWidget.tabText(index) )
            self.tabWidget.setTabText(index,f"🔴")
            self.previous_checked_index = index
            
    # --- Fill TableWidget  
    def load_parameters(self, current_dict , table_index):                                            
        for i, (key, value) in enumerate(current_dict.items()):     
            self.tableWidget= self.findChild(QTableWidget, f"table_{table_index}")
            self.tableWidget.setItem(i, 0, QTableWidgetItem(str(key)))
            self.tableWidget.setItem(i, 1, QTableWidgetItem(str(value)))         


# ------------------------------------------------- Tests     
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window =  OsciTab()
    window.show()
    sys.exit(app.exec())


