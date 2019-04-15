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

import labscript_utils.h5_lock
import h5py

from qtutils import UiLoader
import qtutils.icons
from qtutils.qt import QtWidgets, QtGui, QtCore
import pyqtgraph as pg


from blacs.tab_base_classes import define_state, MODE_MANUAL

from blacs.device_base_class import DeviceTab

import labscript_utils.properties


from time import monotonic


def exp_av(av_old, data_new, dt, tau):
    """Compute the new value of an exponential moving average based on the previous
    average av_old, a new value data_new, a time interval dt and an averaging timescale
    tau. Returns data_new if dt > tau"""
    if dt > tau:
        return data_new
    k = dt / tau
    return k * data_new + (1 - k) * av_old


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
        self.ui.toolButton_nomax.clicked.connect(self.on_reset_rate_clicked)

        self.attributes_dialog = UiLoader().load(attributes_ui_filepath)
        self.attributes_dialog.setParent(self.ui.parent())
        self.attributes_dialog.setWindowFlags(QtCore.Qt.Tool)
        self.attributes_dialog.setWindowTitle("{} attributes".format(self.device_name))
        self.attributes_dialog.pushButton_copy.clicked.connect(self.on_copy_clicked)
        self.attributes_dialog.comboBox.currentIndexChanged.connect(
            self.on_attr_visibility_level_changed
        )
        self.ui.doubleSpinBox_maxrate.valueChanged.connect(self.on_max_rate_changed)

        layout.addWidget(self.ui)
        self.image = pg.ImageView()
        self.image.setSizePolicy(
            QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding
        )
        self.ui.horizontalLayout.addWidget(self.image)
        self.ui.pushButton_stop.hide()
        self.ui.doubleSpinBox_maxrate.hide()
        self.ui.toolButton_nomax.hide()
        self.ui.label_fps.hide()

        # Ensure the GUI reserves space for these widgets even if they are hidden.
        # This prevents the GUI jumping around when buttons are clicked:
        for widget in [
            self.ui.pushButton_stop,
            self.ui.doubleSpinBox_maxrate,
            self.ui.toolButton_nomax,
        ]:
            size_policy = widget.sizePolicy()
            if hasattr(size_policy, 'setRetainSizeWhenHidden'): # Qt 5.2+ only
                size_policy.setRetainSizeWhenHidden(True)
                widget.setSizePolicy(size_policy)

        self.acquiring = False
        self.last_frame_time = None
        self.frame_rate = None

    def get_save_data(self):
        return {
            'attribute_visibility': self.attributes_dialog.comboBox.currentText(),
            'acquiring': self.acquiring,
            'max_rate': self.ui.doubleSpinBox_maxrate.value()
        }

    def restore_save_data(self, save_data):
        self.attributes_dialog.comboBox.setCurrentText(
            save_data.get('attribute_visibility', 'simple')
        )
        if save_data.get('acquiring', False):
            # Begin acquisition
            self.on_continuous_clicked(None)
        self.ui.doubleSpinBox_maxrate.setValue(save_data.get('max_rate', 0))


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
            'MAX_name': connection_table_properties['MAX_name'],
            'orientation': connection_table_properties['orientation'],
            'imaqdx_attributes': device_properties['imaqdx_attributes'],
            'manual_mode_imaqdx_attributes': connection_table_properties[
                'manual_mode_imaqdx_attributes'
            ],
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
        self.ui.doubleSpinBox_maxrate.show()
        self.ui.toolButton_nomax.show()
        self.ui.label_fps.show()
        self.ui.label_fps.setText('? fps')
        self.acquiring = True
        max_fps = self.ui.doubleSpinBox_maxrate.value()
        timeout_ms = int(1000 / max_fps) if max_fps else 0
        self.statemachine_timeout_add(timeout_ms, self.continuous)
        self.continuous()

    def on_stop_clicked(self, button):
        self.ui.pushButton_snap.setEnabled(True)
        self.ui.pushButton_attributes.setEnabled(True)
        self.ui.pushButton_continuous.show()
        self.ui.doubleSpinBox_maxrate.hide()
        self.ui.toolButton_nomax.hide()
        self.ui.pushButton_stop.hide()
        self.ui.label_fps.hide()
        self.acquiring = False
        self.last_frame_time = None
        self.frame_rate = None
        self.statemachine_timeout_remove(self.continuous)

    def on_copy_clicked(self, button):
        text = self.attributes_dialog.plainTextEdit.toPlainText()
        clipboard = QtGui.QApplication.instance().clipboard()
        clipboard.setText(text)

    def on_reset_rate_clicked(self):
        self.ui.doubleSpinBox_maxrate.setValue(0)

    def on_max_rate_changed(self, max_fps):
        if self.acquiring:
            self.statemachine_timeout_remove(self.continuous)
            timeout_ms = int(1000 / max_fps) if max_fps else 0
            self.statemachine_timeout_add(timeout_ms, self.continuous)
            self.frame_rate = None
            self.last_frame_time = None

    @define_state(MODE_MANUAL, queue_state_indefinitely=True, delete_stale_states=True)
    def on_snap_clicked(self, button):
        data = yield (self.queue_work(self.primary_worker, 'snap'))
        if data is not None:
            self.set_image(data)

    @define_state(MODE_MANUAL, queue_state_indefinitely=True, delete_stale_states=True)
    def continuous(self):
        if not self.acquiring:
            return
        data = yield (self.queue_work(self.primary_worker, 'snap'))
        if data is None:
            self.on_stop_clicked(None)
            return
        this_frame_time = monotonic()
        if self.last_frame_time is not None:
            dt = this_frame_time - self.last_frame_time
            if self.frame_rate is not None:
                # Exponential moving average of the frame rate over five seconds:
                self.frame_rate = exp_av(self.frame_rate, 1 / dt, dt, 5.0)
            else:
                self.frame_rate = 1 / dt
            self.ui.label_fps.setText(f"{self.frame_rate:.02f} fps")
        self.last_frame_time = this_frame_time
        self.set_image(data)

    def set_image(self, data):
        if self.image.image is None:
            # First time setting an image. Do autoscaling etc:
            self.image.setImage(data.T)
        else:
            # Updating image. Keep zoom/pan/levels/etc settings.
            self.image.setImage(data.T, autoRange=False, autoLevels=False)
