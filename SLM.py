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

lower_argv = [s.lower() for s in sys.argv]
if 'pyside' in lower_argv:
    # Import Qt
    from PySide.QtCore import *
    from PySide.QtGui import *
    # from PySide.QtUiTools import QUiLoader
elif 'pyqt' in lower_argv:
    from PyQt4.QtCore import *
    from PyQt4.QtGui import *
else:
    try:
        from PyQt4.QtCore import *
        from PyQt4.QtGui import *
    except Exception:
        from PySide.QtCore import *
        from PySide.QtGui import *

class SLMSegment(Device):
    description = 'SLM Segment'
    generation = 3
    def __init__(self, name, parent_device, connection, x, y, width, height):
        # These must be stored before calling the parent class constructor so that the checks in SLM.add_device run correctly
        self.x = x
        self.y = y
        self.width = width
        self.height = height

        self.encoded_image = None
        
        Device.__init__(self, name, parent_device, connection)
         
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
        scene = QGraphicsScene(0,0,1920,1080)
        graphics_view = SLMGraphicsView(scene)
        graphics_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        graphics_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.get_tab_layout().addWidget(graphics_view)
        
        
        self.supports_remote_value_check(True)
        
        self.supports_smart_programming(True) 
        
    def initialise_worker(self):
        self.server = self.BLACS_connection
        self.create_worker("main_worker",SLMWorker,{'server':self.server})
        self.primary_worker = "main_worker"
        
    # This function gets the status of the Pulseblaster from the spinapi,
    # and updates the front panel widgets!
    @define_state(MODE_MANUAL|MODE_BUFFERED|MODE_TRANSITION_TO_BUFFERED|MODE_TRANSITION_TO_MANUAL,True)  
    def status_monitor(self):
        self.status yield(self.queue_work(self._primary_worker,'check_status'))
        
@BLACS_worker
class SLMWorker(Worker):
    def init(self):
        global zprocess; import zprocess
        global shared_drive; import labscript_utils.shared_drive as shared_drive
        
    def check_status(self)
        images = {}
        
        return images

        
# this class is used by both the server that can be launched from this script, and the BLACS tab
from qtutils import *

class SLMGraphicsView(QGraphicsView):
    def __init__(self,*args,**kwargs):
        QGraphicsView.__init__(self,*args,**kwargs)
        self.setStyleSheet("background-color:#000000; border: 0px;")

        self.regions = {}
        self.regions['1'] = {'offset':QPointF(0,0), 'size':QSize(1920/2,1080), 'item':None, 'encoded':''}
        self.regions['2'] = {'offset':QPointF(1920*2/4.,0), 'size':QSize(1920/4,1080/2), 'item':None, 'encoded':''}
        self.regions['3'] = {'offset':QPointF(1920*3/4.,0), 'size':QSize(1920/4,1080/2), 'item':None, 'encoded':''}
        self.regions['4'] = {'offset':QPointF(1920*2/4.,1080/2), 'size':QSize(1920/2,1080/2), 'item':None, 'encoded':''}
        
    @inmain_decorator(wait_for_return=True)
    def initialise(self):
        for region, region_dict in self.regions.items():
            if region_dict['item'] is not None:
                self.scene().removeItem(region_dict['item'])
        
    @inmain_decorator(wait_for_return=True)
    def add_image(self, region, image):
        if region in self.regions:
            region_offset = self.regions[region]['offset']
        else:
            return 'Invalid region sepcified. Region given was %s'%region
            
        
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
        self.scene().addItem(pixmap_item)
        self.regions[region]['item'] = pixmap_item
        self.regions[region]['encoded'] = image
        
        return 'ok'
        
    @inmain_decorator(wait_for_return=True)
    def get_encoded_region(self, region):
        return self.regions[region]['encoded']
        
    def resizeEvent(self, event):
        self.fitInView(self.scene().sceneRect())
        return QGraphicsView.resizeEvent(self, event)
        
        
if __name__ == "__main__":
    
    from zprocess import zmq_get, ZMQServer
    import labscript_utils.shared_drive as shared_drive
        
    class ExperimentServer(ZMQServer):
        def __init__(self, *args, **kwargs):
            ZMQServer.__init__(self, *args, **kwargs)
            self.buffered = False
            
        def handler(self, message):
            # print message
            message_parts = message.split()
            cmd = message_parts[0]
            if cmd == 'initialise':
                self.buffered = False
                window.initialise()
                
                # TODO: Configure regions
            elif cmd == 'transition_to_buffered':
                device_name = message_parts[1]
                h5file = message_parts[2]
                fresh = message_parts[3]
                h5file = shared_drive.path_to_local(h5file)
                
                with h5py.File(h5file, 'r') as hdf5_file:
                    group = hdf5_file['/devices/%s'%device_name]
                    for region in group:
                        if region not in window.regions:
                            ret_message = 'Invalid Region specified in HDF5 file'
                            break
                        # TODO: Check dimensions of regions in HDF5 file match
                        # those of this server
                        # This will eventually be checked in the connection table, but requires a new column in the connection table first
                        if fresh or group[region][0] != window.get_encoded_region(region):
                            ret_message = window.add_image(region, group[region][0])
                        else:
                            ret_message = 'ok'
                            
                        if ret_message != 'ok':
                            break       
                self.buffered = True
            elif cmd == 'transition_to_manual':
                self.buffered = False
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
    experiment_server = ExperimentServer(42522)

    # TODO: make SLM size configurable through command line arguments
    scene = QGraphicsScene(0,0,1920,1080)
    window = SLMGraphicsView(scene)
    window.setAlignment(Qt.AlignLeft | Qt.AlignTop)
    window.show()

    app.exec_()
