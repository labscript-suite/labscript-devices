from labscript import IntermediateDevice, DDS, StaticDDS


class NovaTechDDS9M(IntermediateDevice):
    description = 'NT-DDS9M'
    allowed_children = [DDS, StaticDDS]
    clock_limit = 500e3 # TODO: find out what the actual max clock rate is.
    
    def __init__(self, name, parent_device, clock_type, com_port):
        IntermediateDevice.__init__(self, name, parent_device,clock_type)
        self.BLACS_connection = com_port
    
    def quantise_freq(self,data, device):
        # Ensure that frequencies are within bounds:
        if any(data > 171e6 )  or any(data < 0.1 ):
            raise LabscriptError('%s %s '%(device.description, device.name) +
                              'can only have frequencies between 0.1Hz and 171MHz, ' + 
                              'the limit imposed by %s.'%self.name)
        # It's faster to add 0.5 then typecast than to round to integers first:
        data = array((10*data)+0.5,dtype=uint32)
        scale_factor = 10
        return data, scale_factor
        
    def quantise_phase(self,data,device):
        # ensure that phase wraps around:
        data %= 360
        # It's faster to add 0.5 then typecast than to round to integers first:
        data = array((45.511111111111113*data)+0.5,dtype=uint16)
        scale_factor = 45.511111111111113
        return data, scale_factor
        
    def quantise_amp(self,data,device):
        # ensure that amplitudes are within bounds:
        if any(data > 1 )  or any(data < 0):
            raise LabscriptError('%s %s '%(device.description, device.name) +
                              'can only have amplitudes between 0 and 1 (Volts peak to peak approx), ' + 
                              'the limit imposed by %s.'%self.name)
        # It's faster to add 0.5 then typecast than to round to integers first:
        data = array((1023*data)+0.5,dtype=uint16)
        scale_factor = 1023
        return data, scale_factor
        
    def generate_code(self, hdf5_file):
        DDSs = {}
        for output in self.child_devices:
            # Check that the instructions will fit into RAM:
            if isinstance(output, DDS) and len(output.frequency.raw_output) > 16384 - 2: # -2 to include space for dummy instructions
                raise LabscriptError('%s can only support 16383 instructions. '%self.name +
                                     'Please decrease the sample rates of devices on the same clock, ' + 
                                     'or connect %s to a different pseudoclock.'%self.name)
            try:
                prefix, channel = output.connection.split()
                channel = int(channel)
            except:
                raise LabscriptError('%s %s has invalid connection string: \'%s\'. '%(output.description,output.name,str(output.connection)) + 
                                     'Format must be \'channel n\' with n from 0 to 4.')
            DDSs[channel] = output
        for connection in DDSs:
            if connection in range(4):
                dds = DDSs[connection]   
                dds.frequency.raw_output, dds.frequency.scale_factor = self.quantise_freq(dds.frequency.raw_output, dds)
                dds.phase.raw_output, dds.phase.scale_factor = self.quantise_phase(dds.phase.raw_output, dds)
                dds.amplitude.raw_output, dds.amplitude.scale_factor = self.quantise_amp(dds.amplitude.raw_output, dds)                   
            else:
                raise LabscriptError('%s %s has invalid connection string: \'%s\'. '%(dds.description,dds.name,str(dds.connection)) + 
                                     'Format must be \'channel n\' with n from 0 to 4.')
                                
        dtypes = [('freq%d'%i,uint32) for i in range(2)] + \
                 [('phase%d'%i,uint16) for i in range(2)] + \
                 [('amp%d'%i,uint16) for i in range(2)]
                 
        static_dtypes = [('freq%d'%i,uint32) for i in range(2,4)] + \
                        [('phase%d'%i,uint16) for i in range(2,4)] + \
                        [('amp%d'%i,uint16) for i in range(2,4)]
                        
        if self.clock_type == 'slow clock':
            times = self.parent_device.change_times
        else:
            times = self.parent_device.times[self.clock_type]
        out_table = zeros(len(times),dtype=dtypes)
        out_table['freq0'].fill(1)
        out_table['freq1'].fill(1)
        
        static_table = zeros(1, dtype=static_dtypes)
        static_table['freq2'].fill(1)
        static_table['freq3'].fill(1)
        
        for connection in range(2):
            if not connection in DDSs:
                continue
            dds = DDSs[connection]
            # The last two instructions are left blank, for BLACS
            # to fill in at program time.
            out_table['freq%d'%connection][:] = dds.frequency.raw_output
            out_table['amp%d'%connection][:] = dds.amplitude.raw_output
            out_table['phase%d'%connection][:] = dds.phase.raw_output
        for connection in range(2,4):
            if not connection in DDSs:
                continue
            dds = DDSs[connection]
            static_table['freq%d'%connection] = dds.frequency.raw_output[0]
            static_table['amp%d'%connection] = dds.amplitude.raw_output[0]
            static_table['phase%d'%connection] = dds.phase.raw_output[0]
            
        grp = hdf5_file.create_group('/devices/'+self.name)
        grp.attrs['frequency_scale_factor'] = 10
        grp.attrs['amplitude_scale_factor'] = 1023
        grp.attrs['phase_scale_factor'] = 45.511111111111113
        grp.create_dataset('TABLE_DATA',compression=config.compression,data=out_table) 
        grp.create_dataset('STATIC_DATA',compression=config.compression,data=static_table) 
