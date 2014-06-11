from labscript import StaticAnalogQuantity, Device, LabscriptError
import numpy as np

class ZaberStageTLSR150D(StaticAnalogQuantity):
    minval=0
    maxval=76346
    description = 'Zaber Stage T-LSR150D'
    
class ZaberStageTLSR300D(StaticAnalogQuantity):
    minval=0
    maxval=151937
    description = 'Zaber Stage T-LSR300D'
    
class ZaberStageTLS28M(StaticAnalogQuantity):
    minval=0
    maxval=282879
    description = 'Zaber Stage T-LS28-M'

class ZaberStageController(Device):
    allowed_children = [ZaberStageTLSR150D,ZaberStageTLSR300D,ZaberStageTLS28M]
    generation = 0
    def __init__(self, name,com_port):
        Device.__init__(self, name, None, None)
        self.BLACS_connection = com_port
        
    def generate_code(self, hdf5_file):
        data_dict = {}
        for stage in self.child_devices:
            # Call these functions to finalise the stage, they are standard functions of all subclasses of Output:
            ignore = stage.get_change_times()
            stage.make_timeseries([])
            stage.expand_timeseries()
            connection = [int(s) for s in stage.connection.split() if s.isdigit()][0]
            value = stage.raw_output[0]
            if not stage.minval <= value <= stage.maxval:
                # error, out of bounds
                raise LabscriptError('%s %s has value out of bounds. Set value: %s Allowed range: %s to %s.'%(stage.description,stage.name,str(value),str(stage.minval),str(stage.maxval)))
            if not connection > 0:
                # error, invalid connection number
                raise LabscriptError('%s %s has invalid connection number: %s'%(stage.description,stage.name,str(stage.connection)))
            data_dict[str(stage.connection)] = value
        dtypes = [(conn, int) for conn in data_dict]
        data_array = np.zeros(1, dtype=dtypes)
        for conn in data_dict:
            data_array[0][conn] = data_dict[conn] 
        grp = hdf5_file.create_group('/devices/'+self.name)
        grp.create_dataset('static_values', data=data_array)
