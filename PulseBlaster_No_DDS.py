from labscript_devices.PulseBlaster import PulseBlaster

class PulseBlaster_No_DDS(PulseBlaster):

    description = 'generic DO only Pulseblaster'
    clock_limit = 8.3e6 # can probably go faster
    clock_resolution = 20e-9
    n_flags = 24
    
    def write_pb_inst_to_h5(self, pb_inst, hdf5_file):
        # OK now we squeeze the instructions into a numpy array ready for writing to hdf5:
        pb_dtype = [('flags',int32), ('inst',int32),
                    ('inst_data',int32), ('length',float64)]
        pb_inst_table = empty(len(pb_inst),dtype = pb_dtype)
        for i,inst in enumerate(pb_inst):
            flagint = int(inst['flags'][::-1],2)
            instructionint = self.pb_instructions[inst['instruction']]
            dataint = inst['data']
            delaydouble = inst['delay']
            pb_inst_table[i] = (flagint, instructionint, dataint, delaydouble)
        
        # Okay now write it to the file: 
        group = hdf5_file['/devices/'+self.name]  
        group.create_dataset('PULSE_PROGRAM', compression=config.compression,data = pb_inst_table)         
        group.attrs['stop_time'] = self.stop_time     
        
    def generate_code(self, hdf5_file):
        # Generate the hardware instructions
        hdf5_file.create_group('/devices/'+self.name)
        PseudoClock.generate_code(self, hdf5_file)
        dig_outputs, ignore = self.get_direct_outputs()
        pb_inst = self.convert_to_pb_inst(dig_outputs, [], {}, {}, {})
        self.write_pb_inst_to_h5(pb_inst, hdf5_file) 
