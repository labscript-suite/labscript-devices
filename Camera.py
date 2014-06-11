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

from labscript_devices import labscript_device, BLACS_tab, BLACS_worker
from labscript import DigitalOut, LabscriptError
import numpy as np

@labscript_device
class Camera(DigitalOut):
    description = 'Generic Camera'
    frame_types = ['atoms','flat','dark','fluoro','clean']
    minimum_recovery_time = 0 # To be set by subclasses
    
    def __init__(self, name, parent_device, connection, BIAS_port, serial_number, SDK, effective_pixel_size, exposuretime=None, orientation='side'):
        DigitalOut.__init__(self,name,parent_device,connection)
        self.exposuretime = exposuretime
        self.orientation = orientation
        self.exposures = []
        self.BLACS_connection = BIAS_port
        if isinstance(serial_number,str):
            serial_number = int(serial_number,16)
        self.sn = np.uint64(serial_number)
        self.sdk = str(SDK)
        self.effective_pixel_size = effective_pixel_size
        
    def expose(self,name, t , frametype, exposuretime=None):
        self.go_high(t)
        if exposuretime is None:
            duration = self.exposuretime
        else:
            duration = exposuretime
        if duration is None:
            raise LabscriptError('Camera has not had an exposuretime set as an instantiation argument, ' +
                                 'and one was not specified for this exposure')
        self.go_low(t + duration)
        for exposure in self.exposures:
            start = exposure[1]
            end = start + duration
            # Check for overlapping exposures:
            if start <= t <= end or start <= t+duration <= end:
                raise LabscriptError('%s %s has two overlapping exposures: ' %(self.description, self.name) + \
                                 'one at t = %fs for %fs, and another at t = %fs for %fs.'%(t,duration,start,duration))
            # Check for exposures too close together:
            if abs(start - (t + duration)) < self.minimum_recovery_time or abs((t+duration) - end) < self.minimum_recovery_time:
                raise LabscriptError('%s %s has two exposures closer together than the minimum recovery time: ' %(self.description, self.name) + \
                                 'one at t = %fs for %fs, and another at t = %fs for %fs. '%(t,duration,start,duration) + \
                                 'The minimum recovery time is %fs.'%self.minimum_recovery_time)
        # Check for invalid frame type:                        
        if not frametype in self.frame_types:
            raise LabscriptError('%s is not a valid frame type for %s %s.'%(str(frametype), self.description, self.name) +\
                             'Allowed frame types are: \n%s'%'\n'.join(self.frame_types))
        self.exposures.append((name, t, frametype, duration))
        return duration
    
    def do_checks(self, *args):
        if not self.t0 in self.instructions:
            self.go_low(self.t0)
        DigitalOut.do_checks(self, *args) 
           
    def generate_code(self, hdf5_file):
        table_dtypes = [('name','a256'), ('time',float), ('frametype','a256'), ('exposuretime',float)]
        data = np.array(self.exposures,dtype=table_dtypes)
        group = hdf5_file['devices'].create_group(self.name)
        group.attrs['exposure_time'] = float(self.exposuretime) if self.exposuretime is not None else float('nan')
        group.attrs['orientation'] = self.orientation
        group.attrs['SDK'] = self.sdk
        group.attrs['serial_number'] = self.sn
        group.attrs['effective_pixel_size'] = self.effective_pixel_size
        if self.exposures:
            group.create_dataset('EXPOSURES', data=data)
            
            

import os
from blacs.tab_base_classes import Worker, define_state
from blacs.tab_base_classes import MODE_MANUAL, MODE_TRANSITION_TO_BUFFERED, MODE_TRANSITION_TO_MANUAL, MODE_BUFFERED  

from blacs.device_base_class import DeviceTab

from qtutils import UiLoader

@BLACS_tab
class CameraTab(DeviceTab):
    def initialise_GUI(self):
        layout = self.get_tab_layout()
        ui_filepath = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'camera.ui')
        self.ui = UiLoader().load(ui_filepath)
        layout.addWidget(self.ui)
        
        port = int(self.settings['connection_table'].find_by_name(self.settings["device_name"]).BLACS_connection)
        self.ui.port_label.setText(str(port)) 
        
        self.ui.is_responding.setVisible(False)
        self.ui.is_not_responding.setVisible(False)
        
        self.ui.host_lineEdit.returnPressed.connect(self.update_settings_and_check_connectivity)
        self.ui.use_zmq_checkBox.toggled.connect(self.update_settings_and_check_connectivity)
        self.ui.check_connectivity_pushButton.clicked.connect(self.update_settings_and_check_connectivity)
        
    def get_save_data(self):
        return {'host': str(self.ui.host_lineEdit.text()), 'use_zmq': self.ui.use_zmq_checkBox.isChecked()}
    
    def restore_save_data(self, save_data):
        print 'restore save data running'
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
        self.ui.saying_hello.setVisible(True)
        self.ui.is_responding.setVisible(False)
        self.ui.is_not_responding.setVisible(False)
        kwargs = self.get_save_data()
        responding = yield(self.queue_work(self.primary_worker, 'update_settings_and_check_connectivity', **kwargs))
        self.update_responding_indicator(responding)
        
    def update_responding_indicator(self, responding):
        self.ui.saying_hello.setVisible(False)
        if responding:
            self.ui.is_responding.setVisible(True)
            self.ui.is_not_responding.setVisible(False)
        else:
            self.ui.is_responding.setVisible(False)
            self.ui.is_not_responding.setVisible(True)

@BLACS_worker            
class CameraWorker(Worker):
    def init(self):#, port, host, use_zmq):
#        self.port = port
#        self.host = host
#        self.use_zmq = use_zmq
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
            response = zprocess.zmq_get_raw(self.port, self.host, data='hello')
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
        s.send('hello\r\n')
        response = s.recv(1024)
        s.close()
        if 'hello' in response:
            return True
        else:
            raise Exception('invalid response from server: ' + response)
    
    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):
        h5file = shared_drive.path_to_agnostic(h5file)
        if not self.use_zmq:
            return self.transition_to_buffered_sockets(h5file,self.host, self.port)
        response = zprocess.zmq_get_raw(self.port, self.host, data=h5file)
        if response != 'ok':
            raise Exception('invalid response from server: ' + str(response))
        response = zprocess.zmq_get_raw(self.port, self.host, timeout = 10)
        if response != 'done':
            raise Exception('invalid response from server: ' + str(response))
        return {} # indicates final values of buffered run, we have none
        
    def transition_to_buffered_sockets(self, h5file, host, port):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(120)
        s.connect((host, int(port)))
        s.send('%s\r\n'%h5file)
        response = s.recv(1024)
        if not 'ok' in response:
            s.close()
            raise Exception(response)
        response = s.recv(1024)
        if not 'done' in response:
            s.close()
            raise Exception(response)
        return {} # indicates final values of buffered run, we have none
        
    def transition_to_manual(self):
        if not self.use_zmq:
            return self.transition_to_manual_sockets(self.host, self.port)
        response = zprocess.zmq_get_raw(self.port, self.host, 'done')
        if response != 'ok':
            raise Exception('invalid response from server: ' + str(response))
        response = zprocess.zmq_get_raw(self.port, self.host, timeout = 10)
        if response != 'done':
            raise Exception('invalid response from server: ' + str(response))
        return True # indicates success
        
    def transition_to_manual_sockets(self, host, port):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(120)
        s.connect((host, int(port)))
        s.send('done\r\n')
        response = s.recv(1024)
        if not 'ok' in response:
            s.close()
            raise Exception(response)
        response = s.recv(1024)
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
        response = zprocess.zmq_get_raw(self.port, self.host, 'abort')
        if response != 'done':
            raise Exception('invalid response from server: ' + str(response))
        return True # indicates success 
        
    def abort_sockets(self, host, port):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(120)
        s.connect((host, int(port)))
        s.send('abort\r\n')
        response = s.recv(1024)
        if not 'done' in response:
            s.close()
            raise Exception(response)
        return True # indicates success 
    
    def program_manual(self, values):
        return {}
    
    def shutdown(self):
        return
        
