#####################################################################
#                                                                   #
# /SLM.py                                           #
#                                                                   #
# Copyright 2013, Monash University                                 #
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
import sys

import labscript_utils.h5_lock, h5py

# LABSCRIPT_DEVICES IMPORTS
from labscript_devices import labscript_device, BLACS_tab, BLACS_worker, runviewer_parser

# LABSCRIPT IMPORTS
from labscript import Device, LabscriptError
import numpy as np

# BLACS IMPORTS
from blacs.tab_base_classes import Worker, define_state
from blacs.tab_base_classes import MODE_MANUAL, MODE_TRANSITION_TO_BUFFERED, MODE_TRANSITION_TO_MANUAL, MODE_BUFFERED  

from blacs.device_base_class import DeviceTab     
modules_copy = sys.modules.copy()
if 'PySide' in modules_copy or 'PyQt4' in modules_copy:
    if 'PySide' in sys.modules.copy():
        from PySide.QtCore import *
        from PySide.QtGui import *
    else:
        from PyQt4.QtCore import *
        from PyQt4.QtGui import *
        from PyQt4.QtCore import pyqtSignal as Signal
else:
    lower_argv = [s.lower() for s in sys.argv]
    if 'pyside' in lower_argv:
        # Import Qt
        from PySide.QtCore import *
        from PySide.QtGui import *
        # from PySide.QtUiTools import QUiLoader
    elif 'pyqt' in lower_argv:
        from PyQt4.QtCore import *
        from PyQt4.QtGui import *
        from PyQt4.QtCore import pyqtSignal as Signal
    else:
        try:
            from PyQt4.QtCore import *
            from PyQt4.QtGui import *
            from PyQt4.QtCore import pyqtSignal as Signal
        except Exception:
            from PySide.QtCore import *
            from PySide.QtGui import *

class SLMSegment(Device):
    description = 'SLM Segment'
    generation = 3
    def __init__(self, name, parent_device, connection, x, y, width, height):
        # These must be stored before calling the parent class constructor so that the checks in SLM.add_device run correctly
        property_list = ['x', 'y', 'width', 'height']
        for property_name in property_list:
            setattr(self, property_name, locals()[property_name])
            
        # self.x = x
        # self.y = y
        # self.width = width
        # self.height = height

        self.encoded_image = None
        
        Device.__init__(self, name, parent_device, connection)
        
        # store the properties in the connection table entry for this device
        for property_name in property_list:
            self.set_property(property_name, getattr(self, property_name))
         
    def set_image(self, path):
        if self.encoded_image is not None:
            raise LabscriptError('An image has already been set for SLMSegment %s. You can only set this once per shot.'%self.name)
    
        if not os.path.exists(path):
            raise LabscriptError('Cannot load the image for SLM Segment %s (path: %s)'%(self.name, path))
        
        raw_data = ''        
        with open(path, 'rb') as f:
            raw_data = f.read()

        self.encoded_image = base64.b64encode(raw_data)
    
@labscript_device
class SLM(Device):
    description = 'Spatial Light Modulator'
    allowed_children = [SLMSegment]
    generation = 0
    
    def __init__(self, name, server, port, width, height):
        Device.__init__(self, name, None, None)
        self.BLACS_connection = '%s:%d'%(server, port)
        self.width = width
        self.height = height
        
        # store these properties in the connection table
        self.set_property('width', self.width)
        self.set_property('height', self.height)
    
    def children_intersect(self, child1, child2):
        return False
        return self.regions_intersect(child1.x, child1.y, child1.width, child1.height, child2.x, child2.y, child2.width, child2.height)
    
    def regions_intersect(self, x1, y1, width1, height1, x2, y2, width2, height2):
        points1 = [(x,y) for x in range(x1,x1+width1) for y in range(y1, y1+height1)]
        points2 = [(x,y) for x in range(x2,x2+width2) for y in range(y2, y2+height2)]
        
        points1 = np.array(points1, dtype=[('x',np.int32),('y',np.int32)])
        points2 = np.array(points2, dtype=[('x',np.int32),('y',np.int32)])
        
        if np.intersect1d(points1, points2):
            return True
        else:
            return False
        
    def add_device(self, device):        
        # run checks
        for output in self.child_devices:
            # is the connection (SLM Segment number) unique?
            if device.connection == output.connection:
                raise LabscriptError('%s and %s are both connected to %s of %s.'%(output.name, device.name, output.connection, self.name))
            
            # is the SLM Segment area unique?
            if self.children_intersect(device, output):
                raise LabscriptError('The SLMSegments %s and %s (attached to SLM %s) intersect. SLMSegments must utilise unique pixels of the SLM'%(device.name, output.name, self.name))
                
        # if the device passes the checks, call the parent class function to add it as a child
        Device.add_device(self, device)
                
    def generate_code(self, hdf5_file):
        group = hdf5_file.create_group('/devices/'+self.name)
        Device.generate_code(self, hdf5_file)
        
        for segment in self.child_devices:
            if segment.encoded_image is not None:
                # write the encoded images to the hdf5 file
                region = segment.connection
                
                dataset = group.create_dataset(str(segment.connection),data=segment.encoded_image)
            
                # TODO: Store in generic connection table column
                dataset.attrs['x'] = segment.x
                dataset.attrs['y'] = segment.y
                dataset.attrs['width'] = segment.width
                dataset.attrs['height'] = segment.height
            


     
@BLACS_tab
class SLMTab(DeviceTab):
    
    def initialise_GUI(self):
        # find the connection table object for this device
        self.connection_object = self.connection_table.find_by_name(self.device_name)
        
        # Get the SLM properties from the connection table
        accepted_slm_property_keys = ['width', 'height']
        self.slm_properties = {k:v for k,v in self.connection_object.properties.items() if k in accepted_slm_property_keys}
        
        # Get the region properties from teh connection table and build the dictionary to produce the IMAGE object outputs
        image_properties = {}
        self.regions = {} # dict for worker process
        regions = {} # dict for nicer view of SLM output
        accepted_region_property_keys = ['width', 'height', 'x', 'y']
        for child_name, child in self.connection_object.child_list.items():
            image_properties[child.parent_port] = child.properties
            
            self.regions[child.parent_port] = {k:v for k,v in child.properties.items() if k in accepted_region_property_keys}
            
            x = child.properties['x']
            y = child.properties['y']
            wx = child.properties['width']
            wy = child.properties['height']
            regions[child.parent_port] = {'offset':QPointF(x,y), 'size':QSize(wx,wy), 'item':None, 'encoded':''}
            
        # Create the outputs and widgets and place the widgets in the UI
        self.create_image_outputs(image_properties)
        _,_,_,image_widgets = self.auto_create_widgets()
        # hide the widget views
        for region, widget in image_widgets.items():
            widget._view.hide()
        self.auto_place_widgets(("Regions", image_widgets))
        
        # generate the better looking view
        self.scene = QGraphicsScene(0,0,self.slm_properties['width'],self.slm_properties['height'])
        self.view = SLMGraphicsView(regions, self.scene)
        self.wrapper_objects = {}
        for region in image_widgets:
            self.wrapper_objects[region] = ImageWrapperWidget(self.view, region)
            self._IMAGE[region].add_widget(self.wrapper_objects[region])
        
        self.get_tab_layout().addWidget(self.view)
        
        self.supports_remote_value_check(False)        
        self.supports_smart_programming(True) 
        
    def initialise_workers(self):
        self.server = self.BLACS_connection
        self.create_worker("main_worker",SLMWorker,{'server':self.server, 'regions':self.regions, 'slm_properties':self.slm_properties})
        self.primary_worker = "main_worker"
        
        
@BLACS_worker
class SLMWorker(Worker):
    def init(self):
        global zprocess; import zprocess
        global shared_drive; import labscript_utils.shared_drive as shared_drive
        
        self.host, self.port = self.server.split(':')
        
        data = '%s %d %d %s'%('initialise', self.slm_properties['width'], self.slm_properties['height'], repr(self.regions))
        response = self.send_data(data)
        if response == 'ok':
            return True
        else:
            raise Exception('invalid response from server: ' + str(response))

    def send_data(self, data):
        return zprocess.zmq_get(self.port, self.host, data=data)
    
    def program_manual(self, values):
        for region, value in values.items():
            data = '%s %s %s'%('manual', region, value)
            response = self.send_data(data)
            if response != 'ok':
                raise Exception('Failed to program manual for region %s. Message was: %s'%(region, response))
                
        return {}
        
    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):
        h5file = shared_drive.path_to_agnostic(h5file)
        response = self.send_data("%s %s %s %s"%("transition_to_buffered", device_name, h5file, fresh))
        
        if response != 'ok':
            raise Exception('Failed to transition to manual. Message from server was: %s'%response)
            
        final_values = {}
        for region in initial_values:
            final_values[region] = self.status(region)
            
        return final_values
        
    def transition_to_manual(self):
        reponse = self.send_data("transition_to_manual")
        if response != 'ok':
            raise Exception('Failed to transition to manual.  Message from server was: %s'%response)
            
        return True
        
    def abort(self):
        reponse = self.send_data("transition_to_manual")
        if response != 'ok':
            raise Exception('Failed to abort.  Message from server was: %s'%response)
            
        return True
        
    def abort_buffered(self):
        return self.abort()
        
    def abort_transition_to_buffered(self):
        return self.abort()
        
    def status(self, region):
        return self.send_data("status %s"%region)
        
# this class is used by both the server that can be launched from this script, and the BLACS tab
from qtutils import *

class ImageWrapperWidget(QObject):
    imageUpdated = Signal(str)
    
    def __init__(self, parent, region):
        QObject.__init__(self)
        self._parent = parent
        self.region = region
        self._Image = None
        
    def lock(self, notify_Image=True):
        if self._Image is not None and notify_Image:
            self._Image.lock()
        # self._parent.lock(self.region)
    
    def unlock(self, notify_Image=True):        
        if self._Image is not None and notify_Image:
            self._Image.unlock()
        # self._parent.unlock(self.region)
        
    @property
    def value(self):
        return self._parent.regions[self.region]['encoded']
        
    @value.setter
    def value(self, value):
        self._parent.add_image(self.region, unicode(value))
        self.imageUpdated.emit(unicode(value))
        
    def set_Image(self, Image, notify_old_Image=True, notify_new_Image=True):
        # If we are setting a new Image, remove this widget from the old one (if it isn't None) and add it to the new one (if it isn't None)
        if Image != self._Image:
            if self._Image is not None and notify_old_Image:
                self._Image.remove_widget(self)
            if Image is not None and notify_new_Image:
                Image.add_widget(self)
        # Store a reference to the Image out object
        self._Image = Image
        
    def get_Image(self):
        return self._Image

class SLMGraphicsView(QGraphicsView):
    def __init__(self, regions, *args,**kwargs):
        QGraphicsView.__init__(self,*args,**kwargs)
        self.setStyleSheet("background-color:#000000; border: 0px;")

        self.regions = regions
        # self.regions['1'] = {'offset':QPointF(0,0), 'size':QSize(1920/2,1080), 'item':None, 'encoded':''}
        # self.regions['2'] = {'offset':QPointF(1920*2/4.,0), 'size':QSize(1920/4,1080/2), 'item':None, 'encoded':''}
        # self.regions['3'] = {'offset':QPointF(1920*3/4.,0), 'size':QSize(1920/4,1080/2), 'item':None, 'encoded':''}
        # self.regions['4'] = {'offset':QPointF(1920*2/4.,1080/2), 'size':QSize(1920/2,1080/2), 'item':None, 'encoded':''}
        
    @inmain_decorator(wait_for_return=True)
    def initialise(self, scene, regions):
        for region, region_dict in self.regions.items():
            if region_dict['item'] is not None:
                self.scene().removeItem(region_dict['item'])
        
        self.regions = regions
        self.setScene(scene)
        
    @inmain_decorator(wait_for_return=True)
    def add_image(self, region, image):
        if region in self.regions:
            region_offset = self.regions[region]['offset']
        else:
            return 'Invalid region sepcified. Region given was %s'%region
            
        if unicode(image) != unicode(""):
            decoded_image = base64.b64decode(image)
            pixmap = QPixmap()
            pixmap.loadFromData(decoded_image, flags=Qt.AvoidDither | Qt.ThresholdAlphaDither | Qt.ThresholdDither)
            # print decoded_image
            if pixmap.size() != self.regions[region]['size']:
                return 'Image size for region %s is incorrect. The image must be of size %s. The size was %s'%(region, self.regions[region]['size'], pixmap.size())
        
            pixmap_item = QGraphicsPixmapItem(pixmap)
            pixmap_item.setOffset(region_offset)
        
        
        if self.regions[region]['item'] is not None:
            self.scene().removeItem(self.regions[region]['item'])
            
        if unicode(image) != unicode(""):
            self.scene().addItem(pixmap_item)
            self.regions[region]['item'] = pixmap_item
        else:
            self.regions[region]['item'] = None
            
        self.regions[region]['encoded'] = image
        
        return 'ok'
        
    @inmain_decorator(wait_for_return=True)
    def get_encoded_region(self, region):
        return self.regions[region]['encoded']
        
    def resizeEvent(self, event):
        self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)
        return QGraphicsView.resizeEvent(self, event)
        
        
if __name__ == "__main__":
    
    from zprocess import zmq_get, ZMQServer
    import labscript_utils.shared_drive as shared_drive
        
    class ExperimentServer(ZMQServer):
        def __init__(self, window, *args, **kwargs):
            ZMQServer.__init__(self, *args, **kwargs)
            self.buffered = False
            self.initialised = False
            self.scene = None
            self.window = window            
            
        @inmain_decorator(wait_for_return=True)   
        def initialise(self, params):
            
            width = int(params[0])
            height = int(params[1])
            properties = eval(" ".join(params[2:]))
            
            regions = {}
            for region, prop in properties.items():
                x = prop['x']
                y = prop['y']
                wx = prop['width']
                wy = prop['height']
                regions[region] = {'offset':QPointF(x,y), 'size':QSize(wx,wy), 'item':None, 'encoded':''}
        
            self.scene = QGraphicsScene(0,0,width,height)
            window.initialise(self.scene, regions)
            
            self.initialised = True
            return 'ok'
            
            
        def handler(self, message):
            # print message
            message_parts = message.split(' ')
            cmd = message_parts[0]
            
            if not self.initialised:
                if cmd != 'initialise':
                    return 'Server not yet initialised. Please send the initialise command'
                    
                else:
                    return self.initialise(message_parts[1:])
                    
            
            if cmd == 'initialise':
                self.buffered = False
                return self.initialise(message_parts[1:])
                
            elif cmd == 'transition_to_buffered':
                device_name = message_parts[1]
                h5file = message_parts[2]
                fresh = bool(message_parts[3])
                h5file = shared_drive.path_to_local(h5file)
                
                with h5py.File(h5file, 'r') as hdf5_file:
                    group = hdf5_file['/devices/%s'%device_name]
                    for region in group:
                        if region not in window.regions:
                            ret_message = 'Invalid Region %s specified in HDF5 file'%region
                            break
                        if fresh or group[region][0] != window.get_encoded_region(region):
                            ret_message = window.add_image(region, group[region][0])
                        else:
                            ret_message = 'ok'
                            
                        if ret_message != 'ok':
                            break       
                self.buffered = True
            elif cmd == 'transition_to_manual':
                self.buffered = False
                ret_message = 'ok'
            elif cmd == 'status':
                region = message_parts[1]
                ret_message = window.get_encoded_region(region)
            elif cmd == 'manual':
                if self.buffered:
                    return 'Cannot program a manual picture when in buffered mode'
                region, image = message_parts[1], message_parts[2]
                ret_message = window.add_image(region, image)
            elif cmd == 'hello':
                ret_message = 'hello'
            else:
                ret_message = 'Unknown command %s'%cmd
                
            return ret_message
            
    class ServerGraphicsView(SLMGraphicsView):            
        def keyPressEvent(self,event):
            if event.key() == Qt.Key_F11:
                if self.isFullScreen():
                    self.showNormal()
                else:
                    self.showFullScreen()
                
            return SLMGraphicsView.keyPressEvent(self,event)
            
        # return the resize event to the original
        def resizeEvent(self, event):
            return QGraphicsView.resizeEvent(self, event)
    
    app = QApplication(sys.argv)

    # TODO: make SLM size configurable through command line arguments
    # scene = QGraphicsScene(0,0,1920,1080)
    regions = {}
    window = ServerGraphicsView(regions)
    window.setAlignment(Qt.AlignLeft | Qt.AlignTop)
    window.setWindowFlags(Qt.WindowStaysOnTopHint)
    window.show()
    window.showFullScreen()

    #TODO: configure port
    experiment_server = ExperimentServer(window, 42522)
    
    app.exec_()
