import os

from qtutils.qt.QtCore import *
from qtutils.qt.QtGui import *

from blacs.tab_base_classes import Worker, define_state
from blacs.tab_base_classes import MODE_MANUAL, MODE_TRANSITION_TO_BUFFERED, MODE_TRANSITION_TO_MANUAL, MODE_BUFFERED  

from blacs.device_base_class import DeviceTab

from qtutils import UiLoader
import qtutils.icons

from qtutils.qt import QtWidgets, QtGui, QtCore
import numpy as np
import pyqtgraph as pg


class IMAQdxCameraTab(DeviceTab):
    def initialise_GUI(self):
        layout = self.get_tab_layout()
        ui_filepath = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), 'blacs_tab.ui'
        )
        self.ui = UiLoader().load(ui_filepath)
        layout.addWidget(self.ui)
        self.image = pg.ImageView()
        self.image.setSizePolicy(
            QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding
        )
        self.ui.horizontalLayout.addWidget(self.image)
        self.ui.pushButton_stop.hide()
        self.acquiring = False
        self.ui.pushButton_acquire.clicked.connect(self.on_acquire_clicked)
        self.ui.pushButton_stop.clicked.connect(self.on_stop_clicked)
        self.ui.pushButton_snap.clicked.connect(self.on_snap_clicked)
        self.ui.pushButton_snap.clicked.connect(self.show_attributes)
        # data = np.random.randn(1024, 1024)
        
    def get_save_data(self):
        # TODO: save the settings of the image widget?
        return {}
    
    def restore_save_data(self, save_data):
        # TODO: restore the settings of the image widget?
        pass
            
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
    
    def on_acquire_clicked(self, button):
        self.ui.pushButton_snap.setEnabled(False)
        self.ui.pushButton_acquire.hide()
        self.ui.pushButton_stop.show()
        self.acquiring = True
        self.acquire()

    def on_stop_clicked(self, button):
        self.ui.pushButton_snap.setEnabled(True)
        self.ui.pushButton_acquire.show()
        self.ui.pushButton_stop.hide()
        self.acquiring = False

    @define_state(MODE_MANUAL, queue_state_indefinitely=True, delete_stale_states=True)
    def on_snap_clicked(self, *button):
        data = yield (self.queue_work(self.primary_worker, 'snap'))
        self.image.setImage(data)

    @define_state(MODE_MANUAL, queue_state_indefinitely=True, delete_stale_states=True)
    def acquire(self):
        success = yield (self.queue_work(self.primary_worker, 'start_acquisition'))
        if not success:
            self.on_stop_clicked()
        while self.acquiring:
            data = yield (self.queue_work(self.primary_worker, 'snap'))
            self.image.setImage(data)