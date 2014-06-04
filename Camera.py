from labscript import DigitalOut
import numpy as np
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
