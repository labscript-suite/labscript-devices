from labscript import Device, StaticDDS

class PhaseMatrixQuickSyn(Device):
    description = 'QuickSyn Frequency Synthesiser'
    allowed_children = [StaticDDS]
    generation = 0
    def __init__(self, name,com_port):
        Device.__init__(self, name, None, None)
        self.clock_type = None
        self.BLACS_connection = com_port
        
    def quantise_freq(self,data, device):
        # Ensure that frequencies are within bounds:
        if any(data > 10e9 )  or any(data < 0.5e9 ):
            raise LabscriptError('%s %s '%(device.description, device.name) +
                              'can only have frequencies between 0.5GHz and 10GHz, ' + 
                              'the limit imposed by %s.'%self.name)
        # It's faster to add 0.5 then typecast than to round to integers first (device is programmed in mHz):
        data = array((1000*data)+0.5,dtype=uint64)
        scale_factor = 1000
        return data, scale_factor
    
    
    def generate_code(self, hdf5_file):
        for output in self.child_devices:
            try:
                prefix, channel = output.connection.split()
                channel = int(channel)
            except:
                raise LabscriptError('%s %s has invalid connection string: \'%s\'. '%(output.description,output.name,str(output.connection)) + 
                                     'Format must be \'channel n\' with n equal 0.')
            if channel != 0:
                raise LabscriptError('%s %s has invalid connection string: \'%s\'. '%(output.description,output.name,str(output.connection)) + 
                                     'Format must be \'channel n\' with n equal 0.')
            dds = output
        # Call these functions to finalise stuff:
        ignore = dds.frequency.get_change_times()
        dds.frequency.make_timeseries([])
        dds.frequency.expand_timeseries()
        
        ignore = dds.gate.get_change_times()
        dds.gate.make_timeseries([])
        dds.gate.expand_timeseries()
        
        dds.frequency.raw_output, dds.frequency.scale_factor = self.quantise_freq(dds.frequency.raw_output, dds)
        static_dtypes = [('freq0',uint64)] + \
                        [('gate0',uint16)]
        static_table = zeros(1, dtype=static_dtypes)   
        static_table['freq0'].fill(1)
        static_table['freq0'] = dds.frequency.raw_output[0]
        static_table['gate0'] = dds.gate.raw_output[0]
        grp = hdf5_file.create_group('/devices/'+self.name)
        grp.attrs['frequency_scale_factor'] = 1000
        grp.create_dataset('STATIC_DATA',compression=config.compression,data=static_table)   
