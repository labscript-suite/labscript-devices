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