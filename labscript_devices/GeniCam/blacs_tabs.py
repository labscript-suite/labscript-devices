import os
import json
import time
import ast
import zmq
import threading

import labscript_utils.h5_lock
import h5py

import numpy as np

import qtutils.icons
from qtutils.qt import QtWidgets, QtGui, QtCore

from blacs.tab_base_classes import define_state, MODE_MANUAL
from blacs.device_base_class import DeviceTab

import labscript_utils.properties

from .genicam_widget import GeniCamWidget



def exp_av(av_old, data_new, dt, tau):
    """Compute the new value of an exponential moving average based on the previous
    average av_old, a new value data_new, a time interval dt and an averaging timescale
    tau. Returns data_new if dt > tau"""
    if dt > tau:
        return data_new
    k = dt / tau
    return k * data_new + (1 - k) * av_old


class GeniCamTab(DeviceTab):
    # Subclasses may override this if all they do is replace the worker class with a
    # different one:
    worker_class = 'labscript_devices.GeniCam.blacs_workers.GeniCamWorker'
    # Subclasses may override this to False if camera attributes should be set every
    # shot even if the same values have previously been set:
    use_smart_programming = True

    def initialise_GUI(self):
        layout = self.get_tab_layout()

        self.widget = GeniCamWidget(layout.parentWidget(), self.device_name)

        layout.addWidget(self.widget)

        self.acquiring = False

        self.supports_smart_programming(self.use_smart_programming)

        # image receive params
        self.last_frame_time = None
        self.frame_rate = None

        self.widget.on_continuous_requested.connect(self.start_continuous)
        self.widget.on_stop_requested.connect(self.stop_continuous)
        self.widget.on_continuous_max_change_requested.connect(self.update_max_fps)
        self.widget.on_snap_requested.connect(self.snap)
        self.widget.on_show_attribute_tree_requested.connect(self.get_and_show_attribute_tree)
        self.widget.on_change_attribute_requested.connect(self.set_attributes)

        self.zmq_ctx = zmq.Context()
        self.image_socket = self.zmq_ctx.socket(zmq.REP)
        self.image_socket_port = self.image_socket.bind_to_random_port('tcp://*', min_port=50000, max_port=59999, max_tries=100)

        self.image_recv_thread = threading.Thread(target=self.image_recv_handler, daemon=True)
        self.image_recv_thread.start()

    def get_save_data(self):
        return {
            # TODO 'attribute_visibility': self.attributes_dialog.visibilityComboBox.currentText(),
            'acquiring': self.acquiring,
            'max_rate': self.widget.max_fps,
            'colormap': repr(self.widget.colormap)
        }

    def restore_save_data(self, save_data):
        # TODO
        # self.attributes_dialog.visibilityComboBox.setCurrentText(
        #     save_data.get('attribute_visibility', 'Beginner')
        # )
        self.widget.request_update_max_fps.emit(save_data.get('max_rate', 0))

        if 'colormap' in save_data:
            self.widget.request_update_colormap.emit(ast.literal_eval(save_data['colormap']))

        if save_data.get('acquiring', False):
            # Begin acquisition
            self.start_continuous()

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
            'cti_file': connection_table_properties['cti_file'],
            'serial_number': connection_table_properties['serial_number'],
            'camera_attributes': device_properties['camera_attributes'],
            'manual_mode_camera_attributes': connection_table_properties[
                'manual_mode_camera_attributes'
            ],
            'image_receiver_port': self.image_socket_port,
        }
        self.create_worker(
            'main_worker', self.worker_class, worker_initialisation_kwargs
        )
        self.primary_worker = "main_worker"

    @define_state(MODE_MANUAL, queue_state_indefinitely=True, delete_stale_states=True)
    def snap(self):
        yield (self.queue_work(self.primary_worker, 'snap'))

    def update_max_fps(self):
        if self.acquiring:
            self.stop_continuous()
            self.start_continuous()

    @define_state(MODE_MANUAL, queue_state_indefinitely=True, delete_stale_states=True)
    def start_continuous(self):
        self.acquiring = True
        max_fps = self.widget.max_fps
        dt = 1 / max_fps if max_fps else 0
        yield (self.queue_work(self.primary_worker, 'start_continuous', dt))
        self.widget.request_enter_continuous_mode.emit()

    @define_state(MODE_MANUAL, queue_state_indefinitely=True, delete_stale_states=True)
    def stop_continuous(self):
        yield (self.queue_work(self.primary_worker, 'stop_continuous'))
        self.acquiring = False
        self.widget.request_exit_continuous_mode.emit()

    @define_state(MODE_MANUAL, queue_state_indefinitely=True, delete_stale_states=True)
    def get_and_show_attribute_tree(self):
        attr_tree = yield (self.queue_work(self.primary_worker, 'get_attribute_tuples_as_dict'))
        self.widget.request_show_attribute_tree.emit(attr_tree)

    @define_state(MODE_MANUAL, queue_state_indefinitely=True, delete_stale_states=True)
    def set_attributes(self, attr_dict):
        attr_dict = yield (self.queue_work(self.primary_worker, 'set_attributes', attr_dict))
        self.widget.request_update_attribute_tree.emit(attr_dict)

    def restart(self, *args, **kwargs):
        # Must manually stop the receiving server upon tab restart, otherwise it does
        # not get cleaned up:
        # if self.image_socket:
        #     self.image_socket.close()
        return DeviceTab.restart(self, *args, **kwargs)

    def update_control(self):
        if self.mode == 2:
            # Transitioning to buffered
            # TODO
            pass
        elif self.mode == 4:
            # Transitioning to manual
            # TODO
            pass

    def image_recv_handler(self):
        while True:
            # Acknowledge immediately so that the worker process can begin acquiring the
            # next frame. This increases the possible frame rate since we may render a frame
            # whilst acquiring the next, but does not allow us to accumulate a backlog since
            # only one call to this method may occur at a time.
            md_json, image_data = self.image_socket.recv_multipart()

            self.image_socket.send(b'ok')

            md = json.loads(md_json)
            image = np.frombuffer(memoryview(image_data), dtype=md['dtype'])

            image = image.reshape(md['shape'])
            if len(image.shape) == 3 and image.shape[0] == 1:
                # If only one image given as a 3D array, convert to 2D array:
                image = image.reshape(image.shape[1:])

            this_frame_time = time.time()
            if self.last_frame_time is not None:
                dt = this_frame_time - self.last_frame_time
                if self.frame_rate is not None:
                    # Exponential moving average of the frame rate over 1 second:
                    self.frame_rate = exp_av(self.frame_rate, 1 / dt, dt, 1.0)
                else:
                    self.frame_rate = 1 / dt

            self.last_frame_time = this_frame_time

            self.widget.request_update_image.emit(image)

            # Update fps indicator:
            if self.frame_rate is not None:
                self.widget.request_update_fps.emit(self.frame_rate)
