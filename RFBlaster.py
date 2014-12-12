#####################################################################
#                                                                   #
# RFblaster.py                                                      #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

import os
from labscript import PseudoclockDevice, Pseudoclock, ClockLine, IntermediateDevice, DDS, config, startupinfo, LabscriptError, set_passed_properties
import numpy as np

from labscript_devices import labscript_device, BLACS_tab, BLACS_worker, runviewer_parser

# Define a RFBlasterPseudoclock that only accepts one child clockline
class RFBlasterPseudoclock(Pseudoclock):    
    def add_device(self, device):
        if isinstance(device, ClockLine):
            # only allow one child
            if self.child_devices:
                raise LabscriptError('The pseudoclock of the RFBlaster %s only supports 1 clockline, which is automatically created. Please use the clockline located at %s.clockline'%(self.parent_device.name, self.parent_device.name))
            Pseudoclock.add_device(self, device)
        else:
            raise LabscriptError('You have connected %s to %s (the Pseudoclock of %s), but %s only supports children that are ClockLines. Please connect your device to %s.clockline instead.'%(device.name, self.name, self.parent_device.name, self.name, self.parent_device.name))

@labscript_device
class RFBlaster(PseudoclockDevice):
    description = 'RF Blaster Rev1.1'
    clock_limit = 500e3
    clock_resolution = 13.33333333333333333333e-9
    allowed_children = [RFBlasterPseudoclock]
    
    # TODO: find out what these actually are!
    trigger_delay = 873.75e-6
    wait_day = trigger_delay
    
    @set_passed_properties()
    def __init__(self, name, ip_address, trigger_device=None, trigger_connection=None):
        PseudoclockDevice.__init__(self, name, trigger_device, trigger_connection)
        self.BLACS_connection = ip_address
        
        # create Pseudoclock and clockline
        self._pseudoclock = RFBlasterPseudoclock('%s_pseudoclock'%name, self, 'clock') # possibly a better connection name than 'clock'?
        # Create the internal direct output clock_line
        self._clock_line = ClockLine('%s_clock_line'%name, self.pseudoclock, 'internal')
        # Create the internal intermediate device connected to the above clock line
        # This will have the DDSs of the RFBlaster connected to it
        self._direct_output_device = RFBlasterDirectOutputs('%s_direct_output_device'%name, self._clock_line)
    
    @property
    def pseudoclock(self):
        return self._pseudoclock
    
    @property
    def direct_outputs(self):
        return self._direct_output_device
    
    def add_device(self, device):
        if not self.child_devices and isinstance(device, Pseudoclock):
            PseudoclockDevice.add_device(self, device)
        elif isinstance(device, Pseudoclock):
            raise LabscriptError('The %s %s automatically creates a Pseudoclock because it only supports one. '%(self.description, self.name) +
                                 'Instead of instantiating your own Pseudoclock object, please use the internal' +
                                 ' one stored in %s.pseudoclock'%self.name)
        elif isinstance(device, DDS):
            #TODO: Defensive programming: device.name may not exist!
            raise LabscriptError('You have connected %s directly to %s, which is not allowed. You should instead specify the parent_device of %s as %s.direct_outputs'%(device.name, self.name, device.name, self.name))
        else:
            raise LabscriptError('You have connected %s (class %s) to %s, but %s does not support children with that class.'%(device.name, device.__class__, self.name, self.name))
        
        
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
        PseudoclockDevice.generate_code(self, hdf5_file)
        dtypes = [('time',float),('amp0',float),('freq0',float),('phase0',float),('amp1',float),('freq1',float),('phase1',float)]
        
        times = self.pseudoclock.times[self._clock_line]
        
        data = np.zeros(len(times),dtype=dtypes)
        data['time'] = times
        for dds in self.direct_outputs.child_devices:
            prefix, connection = dds.connection.split()
            data['freq%s'%connection] = dds.frequency.raw_output
            data['amp%s'%connection] = dds.amplitude.raw_output
            data['phase%s'%connection] = dds.phase.raw_output
        group = hdf5_file['devices'].create_group(self.name)
        group.create_dataset('TABLE_DATA',compression=config.compression, data=data)
        
        # Quantise the data and save it to the h5 file:
        quantised_dtypes = [('time',np.int64),
                            ('amp0',np.int32), ('freq0',np.int32), ('phase0',np.int32),
                            ('amp1',np.int32), ('freq1',np.int32), ('phase1',np.int32)]
        quantised_data = np.zeros(len(times),dtype=quantised_dtypes)
        quantised_data['time'] = np.array(c.tT*1e6*data['time']+0.5)
        for dds in range(2):
            # TODO: bounds checking
            # Adding 0.5 to each so that casting to integer rounds:
            quantised_data['freq%d'%dds] = np.array(c.fF*1e-6*data['freq%d'%dds] + 0.5)
            quantised_data['amp%d'%dds]  = np.array((2**c.bitsA - 1)*data['amp%d'%dds] + 0.5)
            quantised_data['phase%d'%dds] = np.array(c.pP*data['phase%d'%dds] + 0.5)
        group.create_dataset('QUANTISED_DATA',compression=config.compression, data=quantised_data)
        # Generate some assembly code and compile it to machine code:
        assembly_group = group.create_group('ASSEMBLY_CODE')
        binary_group = group.create_group('BINARY_CODE')
        diff_group = group.create_group('DIFF_TABLES')
        # When should the RFBlaster wait for a trigger?
        quantised_trigger_times = np.array([c.tT*1e6*t + 0.5 for t in self.trigger_times], dtype=np.int64)
        for dds in range(2):
            abs_table = np.zeros((len(times), 4),dtype=np.int64)
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
                binary_group.create_dataset('DDS%d'%dds, data=np.string_(binary_data))
            finally:
                # Delete the temporary files:
                os.remove(temp_assembly_filepath)
                os.remove(temp_binary_filepath)
                # print 'assembly:', temp_assembly_filepath
                # print 'binary for dds %d on %s:'%(dds,self.name), temp_binary_filepath

                
class RFBlasterDirectOutputs(IntermediateDevice):
    allowed_children = [DDS]
    clock_limit = RFBlaster.clock_limit
    description = 'RFBlaster Direct Outputs'
  
    def add_device(self, device):
        try:
            prefix, number = device.connection.split()
            assert int(number) in range(2)
            assert prefix == 'dds'
        except Exception:
            raise LabscriptError('invalid connection string. Please use the format \'dds n\' with n 0 or 1')
       
        if isinstance(device, DDS):
            # Check that the user has not specified another digital line as the gate for this DDS, that doesn't make sense.
            if device.gate is not None:
                raise LabscriptError('You cannot specify a digital gate ' +
                                     'for a DDS connected to %s. '% (self.name))
                                     
        IntermediateDevice.add_device(self, device)
        
        
        
from blacs.tab_base_classes import Worker, define_state
from blacs.tab_base_classes import MODE_MANUAL, MODE_TRANSITION_TO_BUFFERED, MODE_TRANSITION_TO_MANUAL, MODE_BUFFERED  
from blacs.device_base_class import DeviceTab


@BLACS_tab
class RFBlasterTab(DeviceTab):
    def initialise_GUI(self):
        # Capabilities 
        self.base_units =     {'freq':'Hz',        'amp':'%',         'phase':'Degrees'}
        self.base_min =       {'freq':500000,      'amp':0.0,         'phase':0}
        self.base_max =       {'freq':350000000.0, 'amp':99.99389648, 'phase':360}
        self.base_step =      {'freq':1000000,     'amp':1.0,         'phase':1}
        #TODO: Find out what the amp and phase precision is
        self.base_decimals =  {'freq':1,           'amp':3,           'phase':3}
        self.num_DDS = 2  

        # Create DDS Output objects
        dds_prop = {}
        for i in range(self.num_DDS): # 2 is the number of DDS outputs on this device
            dds_prop['dds %d'%i] = {}
            for subchnl in ['freq', 'amp', 'phase']:
                dds_prop['dds %d'%i][subchnl] = {'base_unit':self.base_units[subchnl],
                                                 'min':self.base_min[subchnl],
                                                 'max':self.base_max[subchnl],
                                                 'step':self.base_step[subchnl],
                                                 'decimals':self.base_decimals[subchnl]
                                                }
            dds_prop['dds %d'%i]['gate'] = {}
                
        # Create the output objects    
        self.create_dds_outputs(dds_prop)        
        # Create widgets for output objects
        dds_widgets,ao_widgets,do_widgets = self.auto_create_widgets()
        # and auto place the widgets in the UI
        self.auto_place_widgets(("DDS Outputs",dds_widgets))
        
        # Store the COM port to be used
        self.address = "http://" + str(self.BLACS_connection) + ":8080"
        
        # Create and set the primary worker
        self.create_worker("main_worker",RFBlasterWorker,{'address':self.address, 'num_DDS':self.num_DDS})
        self.primary_worker = "main_worker"

        # Set the capabilities of this device
        self.supports_remote_value_check(True)
        self.supports_smart_programming(False) 
    
    def get_child_from_connection_table(self, parent_device_name, port):
        # This is a direct output, let's search for it on the internal intermediate device called 
        # RFBlasterDirectOutputs
        if parent_device_name == self.device_name:
            device = self.connection_table.find_by_name(self.device_name)
            pseudoclock = device.child_list[device.child_list.keys()[0]] # there should always be one (and only one) child, the Pseudoclock
            clockline = pseudoclock.child_list[pseudoclock.child_list.keys()[0]] # there should always be one (and only one) child, the clockline
            direct_outputs = clockline.child_list[clockline.child_list.keys()[0]] # There should only be one child of this clock line, the direct outputs
            # look to see if the port is used by a child of the direct outputs
            return DeviceTab.get_child_from_connection_table(self, direct_outputs.name, port)
        else:
            # else it's a child of a DDS, so we can use the default behaviour to find the device
            return DeviceTab.get_child_from_connection_table(self, parent_device_name, port)
    
    # We override this because the RFBlaster doesn't really support remote_value_checking properly
    # Here we specifically do not program the device (it's slow!) nor do we update the last programmed value to the current
    # front panel state. This is because the remote value returned from the RFBlaster is always the last *manual* values programmed.
    @define_state(MODE_BUFFERED,False)
    def transition_to_manual(self,notify_queue,program=False):
        self.mode = MODE_TRANSITION_TO_MANUAL
        
        success = yield(self.queue_work(self._primary_worker,'transition_to_manual'))
        for worker in self._secondary_workers:
            transition_success = yield(self.queue_work(worker,'transition_to_manual'))
            if not transition_success:
                success = False
                # don't break here, so that as much of the device is returned to normal
        
        # Update the GUI with the final values of the run:
        for channel, value in self._final_values.items():
            if channel in self._AO:
                self._AO[channel].set_value(value,program=False)
            elif channel in self._DO:
                self._DO[channel].set_value(value,program=False)
            elif channel in self._DDS:
                self._DDS[channel].set_value(value,program=False)
        
        if success:
            notify_queue.put([self.device_name,'success'])
            self.mode = MODE_MANUAL
        else:
            notify_queue.put([self.device_name,'fail'])
            raise Exception('Could not transition to manual. You must restart this device to continue')
            
    
@BLACS_worker
class RFBlasterWorker(Worker):
    def init(self):
        exec 'from multipart_form import *' in globals()
        exec 'from numpy import *' in globals()
        global h5py; import labscript_utils.h5_lock, h5py
        global urllib2; import urllib2
        global re; import re
        self.timeout = 30 #How long do we wait until we assume that the RFBlaster is dead? (in seconds)
    
        # See if the RFBlaster answers
        urllib2.urlopen(self.address,timeout=self.timeout)
        
        self._last_program_manual_values = {}
        
    def program_manual(self,values):
        self._last_program_manual_values = values
        
        form = MultiPartForm()
        for i in range(self.num_DDS):
            # Program the frequency, amplitude and phase
            form.add_field("a_ch%d_in"%i,str(values['dds %d'%i]['amp']*values['dds %d'%i]['gate']))
            form.add_field("f_ch%d_in"%i,str(values['dds %d'%i]['freq']*1e-6)) # method expects MHz
            form.add_field("p_ch%d_in"%i,str(values['dds %d'%i]['phase']))
            
        form.add_field("set_dds","Set device")
        # Build the request
        req = urllib2.Request(self.address)
        #raise Exception(form_values)
        body = str(form)
        req.add_header('Content-type', form.get_content_type())
        req.add_header('Content-length', len(body))
        req.add_data(body)
        response = str(urllib2.urlopen(req,timeout=self.timeout).readlines())
        return_vals = self.get_web_values(response)
            
        return return_vals
        
    def transition_to_buffered(self,device_name,h5file,initial_values,fresh):
        with h5py.File(h5file,'r') as hdf5_file:
            group = hdf5_file['devices'][device_name]
            #Strip out the binary files and submit to the webserver
            form = MultiPartForm()
            self.final_values = {}
            finalfreq = zeros(self.num_DDS)
            finalamp = zeros(self.num_DDS)
            finalphase = zeros(self.num_DDS)
            for i in range(self.num_DDS):
                #Find the final value from the human-readable part of the h5 file to use for
                #the front panel values at the end
                self.final_values['dds %d'%i] = {'freq':group['TABLE_DATA']["freq%d"%i][-1],
                                                 'amp':group['TABLE_DATA']["amp%d"%i][-1]*100,
                                                 'phase':group['TABLE_DATA']["phase%d"%i][-1],
                                                 'gate':True
                                                }
                data = group['BINARY_CODE/DDS%d'%i].value
                form.add_file_content("pulse_ch%d"%i,"output_ch%d.bin"%i,data)
                
        form.add_field("upload_and_run","Upload and start")
        req = urllib2.Request(self.address)

        body = str(form)
        req.add_header('Content-type', form.get_content_type())
        req.add_header('Content-length', len(body))
        req.add_data(body)
        post_buffered_web_vals = self.get_web_values(str(urllib2.urlopen(req,timeout = self.timeout).readlines()))

        return self.final_values
                 
    def abort_transition_to_buffered(self):
        # TODO: untested (this is probably wrong...)
        form = MultiPartForm()
        #tell the rfblaster to stop
        form.add_field("halt","Halt execution")
        req = urllib2.Request(self.address)
        body = str(form)
        req.add_header('Content-type', form.get_content_type())
        req.add_header('Content-length', len(body))
        req.add_data(body)
        urllib2.urlopen(req,timeout=self.timeout)
        return True
    
    def abort_buffered(self):
        form = MultiPartForm()
        #tell the rfblaster to stop
        form.add_field("halt","Halt execution")
        req = urllib2.Request(self.address)
        body = str(form)
        req.add_header('Content-type', form.get_content_type())
        req.add_header('Content-length', len(body))
        req.add_data(body)
        urllib2.urlopen(req,timeout=self.timeout)
        return True
     
    def transition_to_manual(self):
        # TODO: check that the RF blaster program is finished?
        return True
     
    def get_web_values(self,page): 
        #prepare regular expressions for finding the values:
        search = re.compile(r'name="([fap])_ch(\d+?)_in"\s*?value="([0-9.]+?)"')
        webvalues = re.findall(search,page)
        
        register_name_map = {'f':'freq','a':'amp','p':'phase'}
        newvals = {}
        for i in range(self.num_DDS):
            newvals['dds %d'%i] = {}
        for register,channel,value in webvalues:
            newvals['dds %d'%int(channel)][register_name_map[register]] = float(value)
        for i in range(self.num_DDS):
            if 'dds %d'%i in self._last_program_manual_values and newvals['dds %d'%i]['amp'] == 0:
                newvals['dds %d'%i]['gate'] = self._last_program_manual_values['dds %d'%i]['gate']
            else:
                newvals['dds %d'%i]['gate'] = True
                
            newvals['dds %d'%i]['freq'] *= 1e6 # BLACS expects it in the base unit (Hz)
            
            # if the gate is off, keep the front panel amplitude
            if not newvals['dds %d'%i]['gate']:
                newvals['dds %d'%i]['amp'] = self._last_program_manual_values['dds %d'%i]['amp']
            
        return newvals
    
    def check_remote_values(self):
        #read the webserver page to see what values it puts in the form
        page = str(urllib2.urlopen(self.address,timeout=self.timeout).readlines())
        return self.get_web_values(page)
        
    def shutdown(self):
        # TODO: implement this?
        pass

