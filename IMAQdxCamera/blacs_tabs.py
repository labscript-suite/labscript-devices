import os

from qtutils.qt.QtCore import *
from qtutils.qt.QtGui import *

from blacs.tab_base_classes import Worker, define_state
from blacs.tab_base_classes import MODE_MANUAL, MODE_TRANSITION_TO_BUFFERED, MODE_TRANSITION_TO_MANUAL, MODE_BUFFERED  

from blacs.device_base_class import DeviceTab

from qtutils import UiLoader
import qtutils.icons


class IMAQdxCameraTab(DeviceTab):
    def initialise_GUI(self):
        layout = self.get_tab_layout()
        ui_filepath = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'blacs_tab.ui')
        self.ui = UiLoader().load(ui_filepath)
        layout.addWidget(self.ui)

        # TODO: button to view current attributes. Connect button to function in worker
        # that gets them, and return it as a dict.
        
    def get_save_data(self):
        return {}
        # return {'host': str(self.ui.host_lineEdit.text()), 'use_zmq': self.ui.use_zmq_checkBox.isChecked()}
    
    def restore_save_data(self, save_data):
        pass
        # if save_data:
        #     host = save_data['host']
        #     self.ui.host_lineEdit.setText(host)
        #     if 'use_zmq' in save_data:
        #         use_zmq = save_data['use_zmq']
        #         self.ui.use_zmq_checkBox.setChecked(use_zmq)
        # else:
        #     self.logger.warning('No previous front panel state to restore')
        
        # call update_settings if primary_worker is set
        # this will be true if you load a front panel from the file menu after the tab has started
        # if self.primary_worker:
        #     self.update_settings_and_check_connectivity()
            
    def initialise_workers(self):
        table = self.settings['connection_table']
        properties = table.find_by_name(self.device_name).properties
        worker_initialisation_kwargs = {
            'serial_number': properties['serial_number'],
            'orientation': properties['orientation'],
        }
        self.create_worker(
            'main_worker',
            'labscript_devices.IMAQdxCamera.blacs_workers.IMAQdxCameraWorker',
            worker_initialisation_kwargs,
        )
        self.primary_worker = "main_worker"
       
    # @define_state(MODE_MANUAL, queue_state_indefinitely=True, delete_stale_states=True)
    # def update_settings_and_check_connectivity(self, *args):
    #     icon = QIcon(':/qtutils/fugue/hourglass')
    #     pixmap = icon.pixmap(QSize(16, 16))
    #     status_text = 'Checking...'
    #     self.ui.status_icon.setPixmap(pixmap)
    #     self.ui.server_status.setText(status_text)
    #     kwargs = self.get_save_data()
    #     responding = yield(self.queue_work(self.primary_worker, 'update_settings_and_check_connectivity', **kwargs))
    #     self.update_responding_indicator(responding)
        
    # def update_responding_indicator(self, responding):
    #     if responding:
    #         icon = QIcon(':/qtutils/fugue/tick')
    #         pixmap = icon.pixmap(QSize(16, 16))
    #         status_text = 'Server is responding'
    #     else:
    #         icon = QIcon(':/qtutils/fugue/exclamation')
    #         pixmap = icon.pixmap(QSize(16, 16))
    #         status_text = 'Server not responding'
    #     self.ui.status_icon.setPixmap(pixmap)
    #     self.ui.server_status.setText(status_text)