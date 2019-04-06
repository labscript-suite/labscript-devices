#####################################################################
#                                                                   #
# /labscript_devices/IMAQdxCamera/blacs_tabs.py                     #
#                                                                   #
# Copyright 2019, Monash University and contributors                #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

import os

from qtutils import UiLoader
import qtutils.icons
from qtutils.qt import QtWidgets, QtGui, QtCore
import pyqtgraph as pg

from blacs.tab_base_classes import define_state, MODE_MANUAL

from blacs.device_base_class import DeviceTab

import labscript_utils.properties
import labscript_utils.h5_lock
import h5py


class IMAQdxCameraTab(DeviceTab):
    def initialise_GUI(self):
        layout = self.get_tab_layout()
        ui_filepath = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), 'blacs_tab.ui'
        )
        attributes_ui_filepath = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), 'attributes_dialog.ui'
        )
        self.ui = UiLoader().load(ui_filepath)
        self.ui.pushButton_continuous.clicked.connect(self.on_continuous_clicked)
        self.ui.pushButton_stop.clicked.connect(self.on_stop_clicked)
        self.ui.pushButton_snap.clicked.connect(self.on_snap_clicked)
        self.ui.pushButton_attributes.clicked.connect(self.on_attributes_clicked)

        self.attributes_dialog = UiLoader().load(attributes_ui_filepath)
        self.attributes_dialog.setParent(self.ui.parent())
        self.attributes_dialog.setWindowFlags(QtCore.Qt.Tool)
        self.attributes_dialog.setWindowTitle("{} attributes".format(self.device_name))
        self.attributes_dialog.pushButton_copy.clicked.connect(self.on_copy_clicked)
        self.attributes_dialog.comboBox.currentIndexChanged.connect(
            self.on_attr_visibility_level_changed
        )

        layout.addWidget(self.ui)
        self.image = pg.ImageView()
        self.image.setSizePolicy(
            QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding
        )
        self.ui.horizontalLayout.addWidget(self.image)
        self.ui.pushButton_stop.hide()
        self.acquiring = False

    def get_save_data(self):
        return {'attribute_visibility': self.attributes_dialog.comboBox.currentText()}

    def restore_save_data(self, save_data):
        self.attributes_dialog.comboBox.setCurrentText(
            save_data.get('attribute_visibility', 'simple')
        )

    def initialise_workers(self):
        table = self.settings['connection_table']
        connection_table_properties = table.find_by_name(self.device_name).properties
        # The device properties can vary on a shot-by-shot basis, but at startup we will
        # initially set the values that are configured in the connection table, so they
        # can be used for manual mode acquisition:
        with h5py.File(table.filepath, 'r') as f:
            device_properties = labscript_utils.properties.get(
                f, self.device_name, "device_properties"
            )
        worker_initialisation_kwargs = {
            'serial_number': connection_table_properties['serial_number'],
            'orientation': connection_table_properties['orientation'],
            'imaqdx_attributes': device_properties['imaqdx_attributes'],
        }
        self.create_worker(
            'main_worker',
            'labscript_devices.IMAQdxCamera.blacs_workers.IMAQdxCameraWorker',
            worker_initialisation_kwargs,
        )
        self.primary_worker = "main_worker"

    @define_state(MODE_MANUAL, queue_state_indefinitely=True, delete_stale_states=True)
    def update_attributes(self):
        attributes_text = yield (
            self.queue_work(
                self.primary_worker,
                'get_attributes_as_text',
                self.attributes_dialog.comboBox.currentText(),
            )
        )
        self.attributes_dialog.plainTextEdit.setPlainText(attributes_text)

    def on_attributes_clicked(self, button):
        self.attributes_dialog.show()
        self.on_attr_visibility_level_changed(None)

    def on_attr_visibility_level_changed(self, value):
        self.attributes_dialog.plainTextEdit.setPlainText("Reading attributes...")
        self.update_attributes()

    def on_continuous_clicked(self, button):
        self.ui.pushButton_snap.setEnabled(False)
        self.ui.pushButton_attributes.setEnabled(False)
        self.ui.pushButton_continuous.hide()
        self.ui.pushButton_stop.show()
        self.acquiring = True
        self.continuous()

    def on_stop_clicked(self, button):
        self.ui.pushButton_snap.setEnabled(True)
        self.ui.pushButton_attributes.setEnabled(True)
        self.ui.pushButton_continuous.show()
        self.ui.pushButton_stop.hide()
        self.acquiring = False

    def on_copy_clicked(self, button):
        text = self.attributes_dialog.plainTextEdit.toPlainText()
        clipboard = QtGui.QApplication.instance().clipboard()
        clipboard.setText(text)

    @define_state(MODE_MANUAL, queue_state_indefinitely=True, delete_stale_states=True)
    def on_snap_clicked(self, button):
        data = yield (self.queue_work(self.primary_worker, 'snap'))
        self.set_image(data)

    @define_state(MODE_MANUAL, queue_state_indefinitely=True, delete_stale_states=True)
    def continuous(self):
        while self.acquiring:
            data = yield (self.queue_work(self.primary_worker, 'snap'))
            if data is None:
                self.on_stop_clicked(None)
                return
            self.set_image(data)

    def set_image(self, data):
        if self.image.image is None:
            # First time setting an image. Do autoscaling etc:
            self.image.setImage(data.T)
        else:
            # Updating image. Keep zoom/pan/levels/etc settings.
            self.image.setImage(data.T, autoRange=False, autoLevels=False)
