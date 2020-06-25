#####################################################################
#                                                                   #
# /LightCrafterDMD.py                                               #
#                                                                   #
# Copyright 2017, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

# COMMON IMPORTS
import base64
import os
import struct
import PIL.Image
from io import BytesIO
    
import labscript_utils.h5_lock, h5py

# LABSCRIPT_DEVICES IMPORTS
from labscript_devices import labscript_device, BLACS_tab, BLACS_worker, runviewer_parser

# LABSCRIPT IMPORTS
from labscript import Device, IntermediateDevice, LabscriptError, Output, config
import numpy as np



# BLACS IMPORTS
from blacs.tab_base_classes import Worker, define_state
from blacs.tab_base_classes import MODE_MANUAL, MODE_TRANSITION_TO_BUFFERED, MODE_TRANSITION_TO_MANUAL, MODE_BUFFERED  

from blacs.device_base_class import DeviceTab

from qtutils.qt.QtCore import *
from qtutils.qt.QtGui import *
from qtutils.qt.QtCore import pyqtSignal as Signal


def arr_to_bmp(arr):
    """Convert array to 1 bit BMP, white wherever the array is nonzero, and return a
    bytestring of the BMP data"""
    binary_arr = 255 * (arr != 0).astype(np.uint8)
    im = PIL.Image.fromarray(binary_arr, mode='L').convert('1')
    f = BytesIO()
    im.save(f, "BMP")
    return f.getvalue()


WIDTH = 608
HEIGHT = 684
BLANK_BMP = arr_to_bmp(np.zeros((HEIGHT, WIDTH)))


class ImageSet(Output):
    description = 'A set of images to be displayed on an SLM or DMD'
    width = WIDTH
    height = HEIGHT
    # Set default value to be a black image. Here's a raw BMP!
    default_value = BLANK_BMP
    
    def __init__(self, name, parent_device, connection = 'Mirror'):
        Output.__init__(self, name, parent_device, connection)
        
    def set_array(self, t, arr):
        self.set_image(t, raw=arr_to_bmp(arr))
         
    def set_image(self, t, path=None, raw=None):
        """set an image at the given time, either by a filepath to a bmp file,
        or by a bytestring of bmp data"""
        if raw is not None:
            raw_data = raw
        else:
            if not os.path.exists(path):
                raise LabscriptError('Cannot load the image for DMD output %s (path: %s)'%(self.name, path))
            # First rough check that the path leads to a .bmp file
            if len(path) < 5 or path[-4:] != '.bmp':
                raise LabscriptError('Error loading image for DMD output %s: The image does not appear to be in bmp format(path: %s) Length: %s, end: %s'%(self.name, path, len(path),path[-4:] ))
            with open(path, 'rb') as f:
                raw_data = f.read()
        # Check that the image is a BMP, first two bytes should be "BM"
        if raw_data[0:2] != b"BM":
            raise LabscriptError('Error loading image for DMD output %s: The image does not appear to be in bmp format(path: %s)'%(self.name, path))
        # Check the dimensions match the device, these are stored in bytes 18-21 and 22-25
        width = struct.unpack("<i",raw_data[18:22])[0]
        height = struct.unpack("<i",raw_data[22:26])[0]
        
        if width != self.width or height != self.height:
            raise LabscriptError('Image %s (for DMD output %s) has wrong dimensions. Image dimesions were %s x %s, expected %s x %s'%(path, self.name, width, height, self.width, self.height))
        
        bitdepth = struct.unpack("<h", raw_data[28:30])[0]
        if bitdepth != 1:
            raise LabscriptError("Your image %s is bitdepth %s, but it needs to be 1 for DMD output %s. Please re-save image in appropriate format."%(path,bitdepth,self.name))
        self.add_instruction(t, raw_data)
            
    def expand_timeseries(self,all_times):
        """We have to override the usual expand_timeseries, as it sees strings as iterables that need flattening!
        Luckily for us, we should only ever have individual data points, as we won't be ramping or anything,
        so this function is a lot simpler than the original, as we have more information about the output.
        
        Not 100% sure that this is enough to cover ramps on other devices sharing the clock, come here if there are issues!
        """
        
        self.raw_output = np.array(self.timeseries)
        return
        
        

            
class LightCrafterDMD(IntermediateDevice):
    description = 'LightCrafter DMD controller'
    allowed_children = [ImageSet]
    
    # The following numbers are based on the DLPC300, if there are other models in use with different resolution etc then we'd better make this class more generic.
    # I'm assuming that we'll only be using the device for black & white images with bitdepth of 1.
    max_instructions = 96
    clock_limit = 4000
    width = WIDTH
    height = HEIGHT
    
    def __init__(self, name, parent_device, server = '192.168.1.100', port=21845):
        IntermediateDevice.__init__(self, name, parent_device)
        self.BLACS_connection = '%s:%d'%(server, port)
        
    def add_device(self, device):        
        # run checks
        
        # if the device passes the checks, call the parent class function to add it as a child
        Device.add_device(self, device)
        
        device.width = self.width
        device.height = self.height
                
    def generate_code(self, hdf5_file):
       
        if len(self.child_devices) > 1:
            raise LabscriptError("More than one set of images attached to the LightCrafter")
        output = self.child_devices[0]
        if len(output.raw_output) > self.max_instructions:
            raise LabscriptError("Too many images for the LightCrafter. Your shot contains %s images"%len(output.raw_output))
          
        # Apparently you should use np.void for binary data in a h5 file. Then on the way out, we need to use data.tostring() to decode again.
        out_table = np.void(output.raw_output)
        grp = self.init_device_group(hdf5_file)
        grp.create_dataset('IMAGE_TABLE',compression=config.compression,data=out_table)
        
@BLACS_tab
class LightCrafterTab(DeviceTab):
    # For now, assume only the DLP 0.3 WVGA is supported, fix the image dimensions:
    width = 608
    height = 684
    
    def initialise_GUI(self):
        # find the connection table object for this device
        self.connection_object = self.connection_table.find_by_name(self.device_name)
        
        # Get the region properties from teh connection table and build the dictionary to produce the IMAGE object outputs
        image_properties = {}
        for child_name, child in self.connection_object.child_list.items():
            wx = self.width
            wy = self.height
            image_properties[child.parent_port] = {'width' : wx, 'height' : wy}
            
            
        # Create the outputs and widgets and place the widgets in the UI
        self.create_image_outputs(image_properties)
        _,_,_,image_widgets = self.auto_create_widgets()
        # hide the widget views
        # for region, widget in image_widgets.items():
            # widget._view.hide()
        self.auto_place_widgets(("DMD Image", image_widgets))
        
        # generate the better looking view
        # self.scene = QGraphicsScene(0,0,self.width,self.height)
        # self.view = SLMGraphicsView(regions, self.scene)
        # self.wrapper_objects = {}
        # for region in image_widgets:
            # self.wrapper_objects[region] = ImageWrapperWidget(self.view, region)
            # self._IMAGE[region].add_widget(self.wrapper_objects[region])
        
        # self.get_tab_layout().addWidget(self.view)
        
        self.supports_remote_value_check(False)        
        self.supports_smart_programming(True) 
        
    def initialise_workers(self):
        self.server = self.BLACS_connection
        self.create_worker("main_worker",LightCrafterWorker,{'server':self.server, 'slm_properties':{'width':self.width, 'height':self.height}})
        self.primary_worker = "main_worker"
        
        
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
            return body
    
    
    
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
                    self.send(self.send_packet_type['write'], self.command['pattern_definition'], struct.pack('<B',i) + im.tostring())
                
            self.send(self.send_packet_type['write'], self.command['display_pattern'], struct.pack('<H',0))
            self.send(self.send_packet_type['write'], self.command['start_pattern_sequence'], struct.pack('<B',1))
            self.smart_cache['IMAGE_TABLE'] = table_data
            
            
        # if response != 'ok':
            # raise Exception('Failed to transition to manual. Message from server was: %s'%response)
            
        
        self.final_value = {"None" : base64.b64encode(table_data[-1].tostring())}
        
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
