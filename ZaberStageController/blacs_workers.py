#####################################################################
#                                                                   #
# /labscript_devices/ZaberStageController/blacs_workers.py          #
#                                                                   #
# Copyright 2019, Monash University and contributors                #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

from blacs.tab_base_classes import Worker
from labscript_utils import dedent
import labscript_utils.h5_lock, h5py

from .utils import get_stage_number

class MockZaberInterface(object):
    def __init__(self, port):
        pass

    def move(self, stage_number, position):
        print(f"Mock move stage {stage_number} to position {position}")

    def close(self):
        print(f"mock close")


zaber = None

class ZaberInterface(object):
    def __init__(self, com_port):
        global zaber
        try:
            import zaber.serial as zaber
        except ImportError:
            msg = """Could not import zaber.serial module. Please ensure it is
                installed. It is installable via pip with 'pip install zaber.serial'"""
            raise ImportError(dedent(msg))

        self.port = zaber.AsciiSerial(com_port)

    def move(self, stage_number, position):
        pass

    def close(self):
        pass



class ZaberWorker(Worker):
    def init(self):
        if self.mock:
            self.controller = MockZaberInterface(self.com_port)
        else:
            self.controller = ZaberInterface(self.com_port)
        
    def program_manual(self, values):
        #print "***************programming static*******************"
        #self.stages.move_absolute(settings)
        for connection, value in values.items():
            stage_number = get_stage_number(connection)
            self.controller.move(stage_number, value)
        
        #TODO: return actual position of the zaber stage. Are they readable? Check API
        return values
    
    # TODO: home stage function?

    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):
        with h5py.File(h5file) as hdf5_file:
            group = hdf5_file['/devices/' + device_name]
            if 'static_values' in group:
                data = group['static_values']
                values = {name: data[0][name] for name in data.dtype.names}
            else:
                values = {} 
        
        return self.program_manual(values)
                        
    def transition_to_manual(self):
        return True
    
    def abort_buffered(self):
        return True
        
    def abort_transition_to_buffered(self):
        return True
    
    def shutdown(self):
        self.controller.close()