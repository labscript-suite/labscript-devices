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
import json
from time import perf_counter
import ast
from queue import Empty

import labscript_utils.h5_lock
import h5py

import numpy as np

from qtutils import UiLoader, inmain_decorator
import qtutils.icons
from qtutils.qt import QtWidgets, QtGui, QtCore
import pyqtgraph as pg

from blacs.tab_base_classes import define_state, MODE_MANUAL
from blacs.device_base_class import DeviceTab

import labscript_utils.properties
from labscript_utils.ls_zprocess import ZMQServer




def exp_av(av_old, data_new, dt, tau):
    """Compute the new value of an exponential moving average based on the previous
    average av_old, a new value data_new, a time interval dt and an averaging timescale
    tau. Returns data_new if dt > tau"""
    if dt > tau:
        return data_new
    k = dt / tau
    return k * data_new + (1 - k) * av_old


class ImageReceiver(ZMQServer):
    """ZMQServer that receives images on a zmq.REP socket, replies 'ok', and updates the
    image widget and fps indicator"""

    def __init__(self, image_view, label_fps):
        ZMQServer.__init__(self, port=None, dtype='multipart')
        self.image_view = image_view
        self.label_fps = label_fps
        self.last_frame_time = None
        self.frame_rate = None
        self.update_event = None

    @inmain_decorator(wait_for_return=True)
    def handler(self, data):
        # Acknowledge immediately so that the worker process can begin acquiring the
        # next frame. This increases the possible frame rate since we may render a frame
        # whilst acquiring the next, but does not allow us to accumulate a backlog since
        # only one call to this method may occur at a time.
        self.send([b'ok'])
        md = json.loads(data[0])
        image = np.frombuffer(memoryview(data[1]), dtype=md['dtype'])
        image = image.reshape(md['shape'])
        if len(image.shape) == 3 and image.shape[0] == 1:
            # If only one image given as a 3D array, convert to 2D array:
            image = image.reshape(image.shape[1:])
        this_frame_time = perf_counter()
        if self.last_frame_time is not None:
            dt = this_frame_time - self.last_frame_time
            if self.frame_rate is not None:
                # Exponential moving average of the frame rate over 1 second:
                self.frame_rate = exp_av(self.frame_rate, 1 / dt, dt, 1.0)
            else:
                self.frame_rate = 1 / dt
        self.last_frame_time = this_frame_time
        if self.image_view.image is None:
            # First time setting an image. Do autoscaling etc:
            self.image_view.setImage(image.swapaxes(-1, -2))
        else:
            # Updating image. Keep zoom/pan/levels/etc settings.
            self.image_view.setImage(
                image.swapaxes(-1, -2), autoRange=False, autoLevels=False
            )
        # Update fps indicator:
        if self.frame_rate is not None:
            self.label_fps.setText(f"{self.frame_rate:.01f} fps")

        # Tell Qt to send posted events immediately to prevent a backlog of paint events
        # and other low-priority events. It seems that we cannot make our qtutils
        # CallEvents (which are used to call this method in the main thread) low enough
        # priority to ensure all other occur before our next call to self.handler()
        # runs. This may be because the CallEvents used by qtutils.invoke_in_main have
        # their own event handler (qtutils.invoke_in_main.Caller), perhaps posted event
        # priorities are only meaningful within the context of a single event handler,
        # and not for the Qt event loop as a whole. In any case, this seems to fix it.
        # Manually calling this is usually a sign of bad coding, but I think it is the
        # right solution to this problem. This solves issue #36.
        QtWidgets.QApplication.instance().sendPostedEvents()
        return self.NO_RESPONSE


class IMAQdxCameraTab(DeviceTab):
    # Subclasses may override this if all they do is replace the worker class with a
    # different one:
    worker_class = 'labscript_devices.IMAQdxCamera.blacs_workers.IMAQdxCameraWorker' 
    # Subclasses may override this to False if camera attributes should be set every
    # shot even if the same values have previously been set:
    use_smart_programming = True

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
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
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

        # Start the image receiver ZMQ server:
        self.image_receiver = ImageReceiver(self.image, self.ui.label_fps)
        self.acquiring = False

        self.supports_smart_programming(self.use_smart_programming) 

    def get_save_data(self):
        save_data = {
            'attribute_visibility': self.attributes_dialog.comboBox.currentText(),
            'acquiring': self.acquiring,
            'max_rate': self.ui.doubleSpinBox_maxrate.value(),
            'colormap': repr(self.image.ui.histogram.gradient.saveState())
        }

        # Save info about plot settings if an image is plotted.
        image = self.image.image
        if image is not None:
            # Save the shape and dtype of the image.
            save_data['image_shape'] = repr(image.shape)
            save_data['image_dtype'] = str(image.dtype)

            # Get the view_box to access its settings.
            view_box = self.image.getImageItem().getViewBox()

            # Save x and y ranges.
            targetRange_x, targetRange_y = view_box.targetRange()
            save_data['targetRange_x'] = targetRange_x
            save_data['targetRange_y'] = targetRange_y

            # Save whether the x and y ranges are automatically adjusted.
            autoRange_x, autoRange_y = view_box.autoRangeEnabled()
            save_data['autoRange_x'] = autoRange_x
            save_data['autoRange_y'] = autoRange_y

            # Save color scale limits.
            color_scale_min, color_scale_max = self.image.getLevels()
            save_data['color_scale_min'] = color_scale_min
            save_data['color_scale_max'] = color_scale_max

        return save_data

    def restore_save_data(self, save_data):
        self.attributes_dialog.comboBox.setCurrentText(
            save_data.get('attribute_visibility', 'simple')
        )
        self.ui.doubleSpinBox_maxrate.setValue(save_data.get('max_rate', 0))
        if save_data.get('acquiring', False):
            # Begin acquisition
            self.on_continuous_clicked(None)
        if 'colormap' in save_data:
            self.image.ui.histogram.gradient.restoreState(
                ast.literal_eval(save_data['colormap'])
            )

        # Restore plot settings if they were saved.
        if 'image_shape' in save_data and 'image_dtype' in save_data:
            # Some image must be displayed now, otherwise the plot settings will
            # be overwritten once the first image is displayed. We'll display a
            # mostly blank image of the saved size and data type.
            image_shape = ast.literal_eval(save_data['image_shape'])
            image_dtype = np.dtype(save_data['image_dtype'])
            dummy_image = np.zeros(image_shape, dtype=image_dtype)
            # Make one pixel nonzero to avoid a histogram binning error. This is
            # fixed by in pyqtgraph 0.11 by
            # https://github.com/pyqtgraph/pyqtgraph/pull/767 but this
            # workaround is retained for compatibility with older versions.
            if dummy_image.ndim == 2:
                dummy_image[0, 0] = 1
            if dummy_image.ndim == 3:
                dummy_image[:, 0, 0] = 1
            self.image.setImage(dummy_image)

            # Restore x and y ranges.
            try:
                view_box = self.image.getImageItem().getViewBox()
                view_box.setRange(
                    xRange=save_data['targetRange_x'],
                    yRange=save_data['targetRange_y'],
                )
            except KeyError:
                pass

            # Restore whether the x and y ranges are automatically adjusted.
            try:
                view_box.enableAutoRange(
                    x=save_data['autoRange_x'],
                    y=save_data['autoRange_y'],
                )
            except KeyError:
                pass

            # Restore color scale range.
            try:
                self.image.setLevels(
                    save_data['color_scale_min'],
                    save_data['color_scale_max'],
                )
            except KeyError:
                pass


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
            'camera_attributes': device_properties['camera_attributes'],
            'manual_mode_camera_attributes': connection_table_properties[
                'manual_mode_camera_attributes'
            ],
            'mock': connection_table_properties['mock'],
            'image_receiver_port': self.image_receiver.port,
        }
        self.create_worker(
            'main_worker', self.worker_class, worker_initialisation_kwargs
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
        dt = 1 / max_fps if max_fps else 0
        self.start_continuous(dt)

    def on_stop_clicked(self, button):
        self.ui.pushButton_snap.setEnabled(True)
        self.ui.pushButton_attributes.setEnabled(True)
        self.ui.pushButton_continuous.show()
        self.ui.doubleSpinBox_maxrate.hide()
        self.ui.toolButton_nomax.hide()
        self.ui.pushButton_stop.hide()
        self.ui.label_fps.hide()
        self.acquiring = False
        self.stop_continuous()

    def on_copy_clicked(self, button):
        text = self.attributes_dialog.plainTextEdit.toPlainText()
        clipboard = QtGui.QApplication.instance().clipboard()
        clipboard.setText(text)

    def on_reset_rate_clicked(self):
        self.ui.doubleSpinBox_maxrate.setValue(0)

    def on_max_rate_changed(self, max_fps):
        if self.acquiring:
            self.stop_continuous()
            dt = 1 / max_fps if max_fps else 0
            self.start_continuous(dt)

    @define_state(MODE_MANUAL, queue_state_indefinitely=True, delete_stale_states=True)
    def on_snap_clicked(self, button):
        yield (self.queue_work(self.primary_worker, 'snap'))

    @define_state(MODE_MANUAL, queue_state_indefinitely=True, delete_stale_states=True)
    def start_continuous(self, dt):
        yield (self.queue_work(self.primary_worker, 'start_continuous', dt))

    @define_state(MODE_MANUAL, queue_state_indefinitely=True, delete_stale_states=True)
    def stop_continuous(self):
        yield (self.queue_work(self.primary_worker, 'stop_continuous'))

    def restart(self, *args, **kwargs):
        # Must manually stop the receiving server upon tab restart, otherwise it does
        # not get cleaned up:
        self.image_receiver.shutdown()
        return DeviceTab.restart(self, *args, **kwargs)
