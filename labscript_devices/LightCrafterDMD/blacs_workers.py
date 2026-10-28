#####################################################################
#                                                                   #
# /labscript_devices/LightCrafterDMD/blacs_workers.py               #
#                                                                   #
# Copyright 2017, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
import base64
import struct
import time
import labscript_utils.h5_lock
import h5py
from blacs.tab_base_classes import Worker
from labscript_devices.LightCrafterDMD.labscript_devices import BLANK_BMP


        
        
class LightCrafterWorker(Worker):
    command = {'version' :             b'\x01\x00',
                'display_mode':         b'\x01\x01',
                'static_image':         b'\x01\x05',
                'sequence_setting':     b'\x04\x00',
                'pattern_definition':   b'\x04\x01',
                'start_pattern_sequence': b'\x04\x02',
                'display_pattern' :     b'\x04\x05',
                'advance_pattern_sequence' : b'\x04\x03',
                }
    send_packet_type = {   'read': b'\x04',
                            'write': b'\x02',
                }
    receive_packet_type = {    b'\x00' : 'System Busy',
                                b'\x01' : 'Error',
                                b'\x03' : 'Write response',
                                b'\x05' : 'Read response',
                            }
    flag = {'complete' : b'\x00',
            'beginning' : b'\x01',
            'intermediate' : b'\x02',
            'end': b'\x03'}
            
    error_messages = {  b'\x01' : "Command execution failed with unknown error",
                        b'\x02' : "Invalid command",
                        b'\x03' : "Invalid parameter",
                        b'\x04' : "Out of memory resource",
                        b'\x05' : "Hardware device failure",
                        b'\x06' : "Hardware busy",
                        b'\x07' : "Not Initialized (any of the preconditions for the command is not met",
                        b'\x08' : "Some object referred by the command is not found. For example, a solution name was not found",
                        b'\x09' : "Checksum error",
                        b'\x0A' : "Packet format error due to insufficient or larger than expected payload size",
                        b'\x0B' : "Command continuation error due to incorrect continuation flag"
                        }
    display_mode = {'static' : b'\x00',
                    'pattern': b'\x04',
                    }
    # Packets must be in the form [packet type (1 bit), command (2), flags (1), payload length (2), data (N), checksum (1)]
    
    def init(self):
        global socket; import socket
        global struct; import struct
        self.host, self.port = self.server.split(':')
        self.port = int(self.port)
        self.smart_cache = {'IMAGE_TABLE': ''}
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host,self.port))
        # Initialise it to a static image display
        self.send(self.send_packet_type['write'], self.command['display_mode'], self.display_mode['static'])
        
        # self.program_manual({"None" : base64.b64encode(blank_bmp)})
        
        
        
    
    def send(self, type, command, data):
        packet = b''.join([type,command,self.flag['complete'],struct.pack('<H',len(data)),data])
        packet += struct.pack('<B',sum(bytearray(packet)) % 256) # add the checksum
        self.sock.send(packet)
        return self.receive()
        
    def _receive(self):
        # This function assumes that we are getting a fresh packet, i.e. there is nothing waiting in the buffer
        # First we get the header bits, to see how big the payload will be:
        header = self.sock.recv(6)
        pkt_type = self.receive_packet_type[header[0:1]]
        command = header[1:3]
        flag = header[3:4]
        length = struct.unpack('<H',header[4:6])[0]
        body = self.sock.recv(length + 1)
        checksum = body[-1:]
        body = body[:-1]
        return {'header' : header, 'type' : pkt_type, 'command' : command, 'flag' : flag, 'length' : length, 'body' : body, 'checksum' : checksum}
        
    def receive(self):
        recv = self._receive()
        # Check the type
        while recv['type'] == "System Busy":
            # the system is busy, guess we should try again in 5 seconds?
            time.sleep(5)
            recv = self._receive()
            
        if recv['type'] == "Error":
            # We have an error
            errors = ""
            for e in recv['body']:
                errors+= self.error_messages[e] + "\n"
            
            raise Exception("Error(s) in receive packet: %s"%errors)
        
        
        check = struct.pack('<B',sum(bytearray(recv['header'] + recv['body'])) % 256)
        
        if check != recv['checksum']:
            raise Exception('Incoming packet checksum does not match')
            
        if recv['flag'] != self.flag['complete']:
            raise Exception('Incoming packet is multipart, this is not implemented yet')
        
        if recv['type'] == 'Write response':
            return True
        else:
            return recv['body']
    
    
    
    def program_manual(self, values):
        for region, value in values.items():
            data = value
            data = base64.b64decode(data)
        # Replace empty data with the black picture
        if not data:
            data = BLANK_BMP
        ## Check to see if it's a BMP
        
        
        if data[0:2] != b"BM":
                raise Exception('Error loading image: Image does not appear to be in bmp format (Initial bits are %s)'%data[0:2])
        
        self.send(self.send_packet_type['write'], self.command['display_mode'], self.display_mode['static'])
        self.send(self.send_packet_type['write'], self.command['static_image'], data)
        return {}
        
    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):
        with h5py.File(h5file, 'r') as hdf5_file:
            group = hdf5_file['/devices/'+device_name]
            if 'IMAGE_TABLE' in group:
                table_data = group['IMAGE_TABLE'][:]
        
        
        if table_data is not None:
            oldtable = self.smart_cache['IMAGE_TABLE']
            self.send(self.send_packet_type['write'], self.command['display_mode'], self.display_mode['pattern'])
            num_of_patterns = len(table_data)
            # We will pad the images we send up to a multiple of four:
            padded_num_of_patterns = num_of_patterns + (-num_of_patterns % 4)
            
            # bit depth, number of patterns, invert patterns?, trigger type, trigger delay (4 bytes), trigger period (4 bytes), exposure time (4 bytes), led select
            self.send(self.send_packet_type['write'], self.command['sequence_setting'],  struct.pack('<BBBBiiiB',1,padded_num_of_patterns,0,2,0,0,0,0))
            if fresh or len(oldtable)!=len(table_data) or (oldtable != table_data).any():
                for i in range(padded_num_of_patterns):
                    if i < num_of_patterns:
                        im = table_data[i]
                    else:
                        # Padding uses the final image:
                        im = table_data[-1]
                    self.send(self.send_packet_type['write'], self.command['pattern_definition'], struct.pack('<B',i) + im.tobytes())
                
            self.send(self.send_packet_type['write'], self.command['display_pattern'], struct.pack('<H',0))
            self.send(self.send_packet_type['write'], self.command['start_pattern_sequence'], struct.pack('<B',1))
            self.smart_cache['IMAGE_TABLE'] = table_data
            
            
        # if response != 'ok':
            # raise Exception('Failed to transition to manual. Message from server was: %s'%response)
            
        
        self.final_value = {"None" : base64.b64encode(table_data[-1].tobytes())}
        
        return self.final_value
        
        
    def transition_to_manual(self):
        # Turn off sequence
        self.send(self.send_packet_type['write'], self.command['start_pattern_sequence'], struct.pack('<B',0))
        self.program_manual(self.final_value)
        return True
        
    def abort(self):
        self.send(self.send_packet_type['write'], self.command['start_pattern_sequence'], struct.pack('<B',0))
            
        return True
        
    def abort_buffered(self):
        return self.abort()
        
    def abort_transition_to_buffered(self):
        return self.abort()
        
    def shutdown(self):
        self.sock.close()
