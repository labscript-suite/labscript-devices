#####################################################################
#                                                                   #
# /labscript_devices/Camera.py                                      #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from labscript_devices import BLACS_tab
from labscript import TriggerableDevice, LabscriptError, set_passed_properties
import numpy as np


class Camera(TriggerableDevice):
    description = 'Generic Camera'        
    
    # To be set as instantiation arguments:
    trigger_edge_type = None
    minimum_recovery_time = None
    
    @set_passed_properties(
        property_names = {
            "connection_table_properties": ["BIAS_port"],
            "device_properties": ["serial_number", "SDK", "effective_pixel_size", "exposure_time", "orientation", "trigger_edge_type", "minimum_recovery_time"]}
        )
    def __init__(self, name, parent_device, connection,
                 BIAS_port = 1027, serial_number = 0x0, SDK='', effective_pixel_size=0.0,
                 exposure_time=float('nan'), orientation='side', trigger_edge_type='rising', minimum_recovery_time=0,
                 **kwargs):
                    
        # not a class attribute, so we don't have to have a subclass for each model of camera:
        self.trigger_edge_type = trigger_edge_type
        self.minimum_recovery_time = minimum_recovery_time
        self.exposure_time = exposure_time
        self.orientation = orientation
        self.BLACS_connection = BIAS_port
        if isinstance(serial_number, str) or isinstance(serial_number, bytes):
            serial_number = int(serial_number,16)
        self.sn = np.uint64(serial_number)
        self.sdk = str(SDK)
        self.effective_pixel_size = effective_pixel_size
        self.exposures = []
        
        # DEPRECATED: backward compatibility:
        if 'exposuretime' in kwargs:
            # We will call self.set_property later to overwrite the non-underscored kwarg's default value.
            self.exposure_time = kwargs.pop('exposuretime')
            import sys
            sys.stderr.write('WARNING: Camera\'s keyword argument \'exposuretime\' deprecated. Use \'exposure_time\' instead.\n')
        
        TriggerableDevice.__init__(self, name, parent_device, connection, **kwargs)

        
    def expose(self, name, t , frametype, exposure_time=None):
        if exposure_time is None:
            duration = self.exposure_time
        else:
            duration = exposure_time
        if duration is None:
            raise LabscriptError('Camera %s has not had an exposure_time set as an instantiation argument, '%self.name +
                                 'and one was not specified for this exposure')
        if not duration > 0:
            raise LabscriptError("exposure_time must be > 0, not %s"%str(duration))
        # Only ask for a trigger if one has not already been requested by 
        # another camera attached to the same trigger:
        already_requested = False
        for camera in self.trigger_device.child_devices:
            if camera is not self:
                for _, other_t, _, other_duration in camera.exposures:
                    if t == other_t and duration == other_duration:
                        already_requested = True
        if not already_requested:
            self.trigger_device.trigger(t, duration)
        # Check for exposures too close together (check for overlapping 
        # triggers already performed in self.trigger_device.trigger()):
        start = t
        end = t + duration
        for exposure in self.exposures:
            _, other_t, _, other_duration = exposure
            other_start = other_t
            other_end = other_t + other_duration
            if abs(other_start - end) < self.minimum_recovery_time or abs(other_end - start) < self.minimum_recovery_time:
                raise LabscriptError('%s %s has two exposures closer together than the minimum recovery time: ' %(self.description, self.name) + \
                                     'one at t = %fs for %fs, and another at t = %fs for %fs. '%(t,duration,start,duration) + \
                                     'The minimum recovery time is %fs.'%self.minimum_recovery_time)
        self.exposures.append((name, t, frametype, duration))
        return duration
    
    def do_checks(self):
        # Check that all Cameras sharing a trigger device have exposures when we have exposures:
        for camera in self.trigger_device.child_devices:
            if camera is not self:
                for exposure in self.exposures:
                    if exposure not in camera.exposures:
                        _, start, _, duration = exposure
                        raise LabscriptError('Cameras %s and %s share a trigger. ' % (self.name, camera.name) + 
                                             '%s has an exposure at %fs for %fs, ' % (self.name, start, duration) +
                                             'but there is no matching exposure for %s. ' % camera.name +
                                             'Cameras sharing a trigger must have identical exposure times and durations.')
                        
    def generate_code(self, hdf5_file):
        self.do_checks()
        table_dtypes = [('name','a256'), ('time',float), ('frametype','a256'), ('exposure_time',float)]
        data = np.array(self.exposures,dtype=table_dtypes)

        group = self.init_device_group(hdf5_file)

        if self.exposures:
            group.create_dataset('EXPOSURES', data=data)
            
        # DEPRECATED backward campatibility for use of exposuretime keyword argument instead of exposure_time:
        self.set_property('exposure_time', self.exposure_time, location='device_properties', overwrite=True)
            
            

import os

from qtutils.qt.QtCore import *
from qtutils.qt.QtGui import *

from blacs.tab_base_classes import Worker, define_state
from blacs.tab_base_classes import MODE_MANUAL, MODE_TRANSITION_TO_BUFFERED, MODE_TRANSITION_TO_MANUAL, MODE_BUFFERED  

from blacs.device_base_class import DeviceTab

from qtutils import UiLoader
import qtutils.icons

@BLACS_tab
class CameraTab(DeviceTab):
    def initialise_GUI(self):
        layout = self.get_tab_layout()
        ui_filepath = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'camera.ui')
        self.ui = UiLoader().load(ui_filepath)
        layout.addWidget(self.ui)
        
        port = int(self.settings['connection_table'].find_by_name(self.settings["device_name"]).BLACS_connection)
        self.ui.port_label.setText(str(port)) 
        
        self.ui.check_connectivity_pushButton.setIcon(QIcon(':/qtutils/fugue/arrow-circle'))
        
        self.ui.host_lineEdit.returnPressed.connect(self.update_settings_and_check_connectivity)
        self.ui.use_zmq_checkBox.toggled.connect(self.update_settings_and_check_connectivity)
        self.ui.check_connectivity_pushButton.clicked.connect(self.update_settings_and_check_connectivity)
        
    def get_save_data(self):
        return {'host': str(self.ui.host_lineEdit.text()), 'use_zmq': self.ui.use_zmq_checkBox.isChecked()}
    
    def restore_save_data(self, save_data):
        if save_data:
            host = save_data['host']
            self.ui.host_lineEdit.setText(host)
            if 'use_zmq' in save_data:
                use_zmq = save_data['use_zmq']
                self.ui.use_zmq_checkBox.setChecked(use_zmq)
        else:
            self.logger.warning('No previous front panel state to restore')
        
        # call update_settings if primary_worker is set
        # this will be true if you load a front panel from the file menu after the tab has started
        if self.primary_worker:
            self.update_settings_and_check_connectivity()
            
    def initialise_workers(self):
        worker_initialisation_kwargs = {'port': self.ui.port_label.text()}
        self.create_worker("main_worker", CameraWorker, worker_initialisation_kwargs)
        self.primary_worker = "main_worker"
        self.update_settings_and_check_connectivity()
       
    @define_state(MODE_MANUAL, queue_state_indefinitely=True, delete_stale_states=True)
    def update_settings_and_check_connectivity(self, *args):
        icon = QIcon(':/qtutils/fugue/hourglass')
        pixmap = icon.pixmap(QSize(16, 16))
        status_text = 'Checking...'
        self.ui.status_icon.setPixmap(pixmap)
        self.ui.server_status.setText(status_text)
        kwargs = self.get_save_data()
        responding = yield(self.queue_work(self.primary_worker, 'update_settings_and_check_connectivity', **kwargs))
        self.update_responding_indicator(responding)
        
    def update_responding_indicator(self, responding):
        if responding:
            icon = QIcon(':/qtutils/fugue/tick')
            pixmap = icon.pixmap(QSize(16, 16))
            status_text = 'Server is responding'
        else:
            icon = QIcon(':/qtutils/fugue/exclamation')
            pixmap = icon.pixmap(QSize(16, 16))
            status_text = 'Server not responding'
        self.ui.status_icon.setPixmap(pixmap)
        self.ui.server_status.setText(status_text)


class CameraWorker(Worker):
    def init(self):
        global socket; import socket
        global zmq; import zmq
        global zprocess; import zprocess
        global shared_drive; import labscript_utils.shared_drive as shared_drive
        
        self.host = ''
        self.use_zmq = False
        
    def update_settings_and_check_connectivity(self, host, use_zmq):
        self.host = host
        self.use_zmq = use_zmq
        if not self.host:
            return False
        if not self.use_zmq:
            return self.initialise_sockets(self.host, self.port)
        else:
            response = zprocess.zmq_get_string(self.port, self.host, data='hello')
            if response == 'hello':
                return True
            else:
                raise Exception('invalid response from server: ' + str(response))
                
    def initialise_sockets(self, host, port):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        assert port, 'No port number supplied.'
        assert host, 'No hostname supplied.'
        assert str(int(port)) == port, 'Port must be an integer.'
        s.settimeout(10)
        s.connect((host, int(port)))
        s.send(b'hello\r\n')
        response = s.recv(1024).decode('utf8')
        s.close()
        if 'hello' in response:
            return True
        else:
            raise Exception('invalid response from server: ' + response)
    
    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):
        h5file = shared_drive.path_to_agnostic(h5file)
        if not self.use_zmq:
            return self.transition_to_buffered_sockets(h5file,self.host, self.port)
        response = zprocess.zmq_get_string(self.port, self.host, data=h5file)
        if response != 'ok':
            raise Exception('invalid response from server: ' + str(response))
        response = zprocess.zmq_get_string(self.port, self.host, timeout = 10)
        if response != 'done':
            raise Exception('invalid response from server: ' + str(response))
        return {} # indicates final values of buffered run, we have none
        
    def transition_to_buffered_sockets(self, h5file, host, port):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(120)
        s.connect((host, int(port)))
        s.send(b'%s\r\n' % h5file.encode('utf8'))
        response = s.recv(1024).decode('utf8')
        if not 'ok' in response:
            s.close()
            raise Exception(response)
        response = s.recv(1024).decode('utf8')
        if not 'done' in response:
            s.close()
            raise Exception(response)
        return {} # indicates final values of buffered run, we have none
        
    def transition_to_manual(self):
        if not self.use_zmq:
            return self.transition_to_manual_sockets(self.host, self.port)
        response = zprocess.zmq_get_string(self.port, self.host, 'done')
        if response != 'ok':
            raise Exception('invalid response from server: ' + str(response))
        response = zprocess.zmq_get_string(self.port, self.host, timeout = 10)
        if response != 'done':
            raise Exception('invalid response from server: ' + str(response))
        return True # indicates success
        
    def transition_to_manual_sockets(self, host, port):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(120)
        s.connect((host, int(port)))
        s.send(b'done\r\n')
        response = s.recv(1024).decode('utf8')
        if response != 'ok\r\n':
            s.close()
            raise Exception(response)
        response = s.recv(1024).decode('utf8')
        if not 'done' in response:
            s.close()
            raise Exception(response)
        return True # indicates success
        
    def abort_buffered(self):
        return self.abort()
        
    def abort_transition_to_buffered(self):
        return self.abort()
    
    def abort(self):
        if not self.use_zmq:
            return self.abort_sockets(self.host, self.port)
        response = zprocess.zmq_get_string(self.port, self.host, 'abort')
        if response != 'done':
            raise Exception('invalid response from server: ' + str(response))
        return True # indicates success 
        
    def abort_sockets(self, host, port):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(120)
        s.connect((host, int(port)))
        s.send(b'abort\r\n')
        response = s.recv(1024).decode('utf8')
        if not 'done' in response:
            s.close()
            raise Exception(response)
        return True # indicates success 
    
    def program_manual(self, values):
        return {}
    
    def shutdown(self):
        return
        
