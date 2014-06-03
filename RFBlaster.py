from labscript import PseudoClock

class RFBlaster(PseudoClock):
    description = 'RF Blaster Rev1.1'
    clock_limit = 500e3
    clock_resolution = 13.33333333333333333333e-9
    clock_type = 'fast clock'
    allowed_children = [DDS]
    
    # TODO: find out what these actually are!
    trigger_delay = 873.75e-6
    wait_day = trigger_delay
    
    def __init__(self, name, ip_address, trigger_device=None, trigger_connection=None):
        PseudoClock.__init__(self, name, trigger_device, trigger_connection)
        self.BLACS_connection = ip_address
    
    def add_device(self, device):
        try:
            prefix, number = device.connection.split()
            assert int(number) in range(2)
            assert prefix == 'dds'
        except Exception:
            raise LabscriptError('invalid connection string. Please use the format \'dds n\' with n 0 or 1')
        PseudoClock.add_device(self, device)
        
    def generate_code(self, hdf5_file):
        from rfblaster import caspr
        import rfblaster.rfjuice
        rfjuice_folder = os.path.dirname(rfblaster.rfjuice.__file__)
        
        import rfblaster.rfjuice.const as c
        from rfblaster.rfjuice.cython.make_diff_table import make_diff_table
        from rfblaster.rfjuice.cython.compile import compileD
        # from rfblaster.rfjuice.compile import compileD
        import tempfile
        from subprocess import Popen, PIPE
        
        # Generate clock and save raw instructions to the h5 file:
        PseudoClock.generate_code(self, hdf5_file)
        dtypes = [('time',float),('amp0',float),('freq0',float),('phase0',float),('amp1',float),('freq1',float),('phase1',float)]
        data = zeros(len(self.times[self.clock_type]),dtype=dtypes)
        data['time'] = self.times[self.clock_type]
        for dds in self.child_devices:
            prefix, connection = dds.connection.split()
            data['freq%s'%connection] = dds.frequency.raw_output
            data['amp%s'%connection] = dds.amplitude.raw_output
            data['phase%s'%connection] = dds.phase.raw_output
        group = hdf5_file['devices'].create_group(self.name)
        group.create_dataset('TABLE_DATA',compression=config.compression, data=data)
        
        # Quantise the data and save it to the h5 file:
        quantised_dtypes = [('time',int64),('amp0',int32),('freq0',int32),('phase0',int32),('amp1',int32),('freq1',int32),('phase1',int32)]
        quantised_data = zeros(len(self.times[self.clock_type]),dtype=quantised_dtypes)
        quantised_data['time'] = array(c.tT*1e6*data['time']+0.5)
        for dds in range(2):
            # TODO: bounds checking
            # Adding 0.5 to each so that casting to integer rounds:
            quantised_data['freq%d'%dds] = array(c.fF*1e-6*data['freq%d'%dds] + 0.5)
            quantised_data['amp%d'%dds]  = array((2**c.bitsA - 1)*data['amp%d'%dds] + 0.5)
            quantised_data['phase%d'%dds] = array(c.pP*data['phase%d'%dds] + 0.5)
        group.create_dataset('QUANTISED_DATA',compression=config.compression, data=quantised_data)
        # Generate some assembly code and compile it to machine code:
        assembly_group = group.create_group('ASSEMBLY_CODE')
        binary_group = group.create_group('BINARY_CODE')
        diff_group = group.create_group('DIFF_TABLES')
        # When should the RFBlaster wait for a trigger?
        quantised_trigger_times = array([c.tT*1e6*t + 0.5 for t in self.trigger_times], dtype=int64)
        for dds in range(2):
            abs_table = zeros((len(self.times[self.clock_type]), 4),dtype=int64)
            abs_table[:,0] = quantised_data['time']
            abs_table[:,1] = quantised_data['amp%d'%dds]
            abs_table[:,2] = quantised_data['freq%d'%dds]
            abs_table[:,3] = quantised_data['phase%d'%dds]
            
            # split up the table into chunks delimited by trigger times:
            abs_tables = []
            for i, t in enumerate(quantised_trigger_times):
                subtable = abs_table[abs_table[:,0] >= t]
                try:
                    next_trigger_time = quantised_trigger_times[i+1]
                except IndexError:
                    # No next trigger time
                    pass
                else:
                    subtable = subtable[subtable[:,0] < next_trigger_time]
                subtable[:,0] -= t
                abs_tables.append(subtable)

            # convert to diff tables:
            diff_tables = [make_diff_table(tab) for tab in abs_tables]
            # Create temporary files, get their paths, and close them:
            with tempfile.NamedTemporaryFile(delete=False) as f:
                temp_assembly_filepath = f.name
            with tempfile.NamedTemporaryFile(delete=False) as f:
                temp_binary_filepath = f.name
                
            try:
                # Compile to assembly:
                with open(temp_assembly_filepath,'w') as assembly_file:
                    for i, dtab in enumerate(diff_tables):
                        compileD(dtab, assembly_file, init=(i == 0),
                                 jump_to_start=(i == 0),
                                 jump_from_end=False,
                                 close_end=(i == len(diff_tables) - 1),
                                 local_loop_pre = str(i),
                                 set_defaults = (i==0))
                # Save the assembly to the h5 file:
                with open(temp_assembly_filepath,) as assembly_file:
                    assembly_code = assembly_file.read()
                    assembly_group.create_dataset('DDS%d'%dds, data=assembly_code)
                    for i, diff_table in enumerate(diff_tables):
                        diff_group.create_dataset('DDS%d_difftable%d'%(dds,i), compression=config.compression, data=diff_table)
                # compile to binary:
                compilation = Popen([caspr,temp_assembly_filepath,temp_binary_filepath],
                                     stdout=PIPE, stderr=PIPE, cwd=rfjuice_folder,startupinfo=startupinfo)
                stdout, stderr = compilation.communicate()
                if compilation.returncode:
                    print stdout
                    raise LabscriptError('RFBlaster compilation exited with code %d\n\n'%compilation.returncode + 
                                         'Stdout was:\n %s\n'%stdout + 'Stderr was:\n%s\n'%stderr)
                # Save the binary to the h5 file:
                with open(temp_binary_filepath,'rb') as binary_file:
                    binary_data = binary_file.read()
                # has to be numpy.string_ (string_ in this namespace,
                # imported from pylab) as python strings get stored
                # as h5py as 'variable length' strings, which 'cannot
                # contain embedded nulls'. Presumably our binary data
                # must contain nulls sometimes. So this crashes if we
                # don't convert to a numpy 'fixes length' string:
                binary_group.create_dataset('DDS%d'%dds, data=string_(binary_data))
            finally:
                # Delete the temporary files:
                os.remove(temp_assembly_filepath)
                os.remove(temp_binary_filepath)
                # print 'assembly:', temp_assembly_filepath
                # print 'binary for dds %d on %s:'%(dds,self.name), temp_binary_filepath
