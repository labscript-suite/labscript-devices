#####################################################################
#                                                                   #
# /labscript_devices/LightCrafterDMD/labscript_devices.py           #
#                                                                   #
# Copyright 2017, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
import os
import struct
import PIL.Image
from io import BytesIO
from labscript import Device, IntermediateDevice, LabscriptError, Output, config
import numpy as np


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
    """bytes: A black image.

    Raw bitmap data hidden from docs.

    :meta hide-value:
    """
    
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
          
        # Apparently you should use np.void for binary data in a h5 file. Then on the way out, we need to use data.tobytes() to decode again.
        out_table = np.void(output.raw_output)
        grp = self.init_device_group(hdf5_file)
        grp.create_dataset('IMAGE_TABLE',compression=config.compression,data=out_table)
