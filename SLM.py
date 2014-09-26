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
import base64
import os

from labscript_devices import labscript_device, BLACS_tab, BLACS_worker, runviewer_parser

import numpy as np

import labscript_utils.h5_lock, h5py

from labscript import Device, LabscriptError

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
            

