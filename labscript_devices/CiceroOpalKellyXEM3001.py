#####################################################################
#                                                                   #
# /CiceroOpalKellyXEM3001.py                                        #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################

from labscript import Device, PseudoclockDevice, Pseudoclock, ClockLine, config, LabscriptError, set_passed_properties, compiler, IntermediateDevice, WaitMonitor, DigitalOut
from labscript_devices import runviewer_parser, BLACS_tab, BLACS_worker, labscript_device

import numpy as np
import labscript_utils.h5_lock, h5py
import labscript_utils.properties
from labscript_utils.connections import _ensure_str

#
# Helper functions
#
def int_to_bytes(n, m):
    # converts the integer n to m bytes in Big Endian format
    out = [(n>>(i*8))&0xFF for i in range(m-1,-1,-1)]
    return out
    
def bits_to_int(m, *args):
    # converts a set of sequences of bits (aka a set of ints), each of length m, to a single integer. first entry in args is least significant
    total = 0
    for i, byte in enumerate(args):
        total += byte << (m*i)
    return total
    
def add_instruction_to_bytearray(data, instruction, on, off, reps):
    on_period = int_to_bytes(on, 6)
    off_period = int_to_bytes(off, 6)
    reps = int_to_bytes(reps, 4)
    
    offset = 16*instruction
    
    # Now convert to little endian format with 16-bit words
    # Bytes 0-5 are for on_period (in multiples of clock period)
    data[offset+0] = on_period[1]
    data[offset+1] = on_period[0]
    data[offset+2] = on_period[3]
    data[offset+3] = on_period[2]
    data[offset+4] = on_period[5]
    data[offset+5] = on_period[4]
    # Bytes 6-11 are for on_period (in multiples of clock period)
    data[offset+6] = off_period[1]
    data[offset+7] = off_period[0]
    data[offset+8] = off_period[3]
    data[offset+9] = off_period[2]
    data[offset+10] = off_period[5]
    data[offset+11] = off_period[4]
    # Bytes 12-15 are for number of reps
    data[offset+12] = reps[1]
    data[offset+13] = reps[0]
    data[offset+14] = reps[3]
    data[offset+15] = reps[2]   
    
        
# Define a CiceroOpalKellyXEM3001Clock that only accepts one child clockline
class CiceroOpalKellyXEM3001Pseudoclock(Pseudoclock):    
    def add_device(self, device):
        if isinstance(device, ClockLine):
            # only allow one child
            if self.child_devices:
                raise LabscriptError('The pseudoclock of the CiceroOpalKellyXEM3001 %s only supports 1 clockline, which is automatically created. Please use the clockline located at %s.clockline'%(self.pseudoclock_device.name, self.pseudoclock_device.name))
            Pseudoclock.add_device(self, device)
        else:
            raise LabscriptError('You have connected %s to %s (the Pseudoclock of %s), but %s only supports children that are ClockLines. Please connect your device to %s.clockline instead.'%(device.name, self.name, self.pseudoclock_device.name, self.name, self.pseudoclock_device.name))
        
    
#
# Define dummy pseudoclock/clockline/intermediatedevice to trick wait monitor
# since everything is handled internally in this device
#
class CiceroOpalKellyXEM3001DummyPseudoclock(Pseudoclock):
    def add_device(self, device):
        if isinstance(device, CiceroOpalKellyXEM3001DummyClockLine):
            if self.child_devices:
                raise LabscriptError('You are trying to access the special, dummy, PseudoClock of the CiceroOpalKellyXEM3001 %s. This is for internal use only.'%(self.pseudoclock_device.name))
            Pseudoclock.add_device(self, device)
        else:
            raise LabscriptError('You are trying to access the special, dummy, PseudoClock of the CiceroOpalKellyXEM3001 %s. This is for internal use only.'%(self.pseudoclock_device.name))
            
    # do nothing, this is a dummy class!
    def generate_code(self, *args, **kwargs):
        pass
        

class CiceroOpalKellyXEM3001DummyClockLine(ClockLine):
    def add_device(self, device):
        if isinstance(device, CiceroOpalKellyXEM3001DummyIntermediateDevice):
            if self.child_devices:
                raise LabscriptError('You are trying to access the special, dummy, ClockLine of the CiceroOpalKellyXEM3001 %s. This is for internal use only.'%(self.pseudoclock_device.name))
            ClockLine.add_device(self, device)
        else:
            raise LabscriptError('You are trying to access the special, dummy, ClockLine of the CiceroOpalKellyXEM3001 %s. This is for internal use only.'%(self.pseudoclock_device.name))
    
    # do nothing, this is a dummy class!
    def generate_code(self, *args, **kwargs):
        pass
 
class CiceroOpalKellyXEM3001DummyIntermediateDevice(IntermediateDevice):
    def add_device(self, device):
        if isinstance(device, WaitMonitor):
            IntermediateDevice.add_device(self, device)
        else:
            raise LabscriptError('You can only connect an instance of WaitMonitor to the device %s.internal_wait_monitor_outputs'%(self.pseudoclock_device.name))
            
    # do nothing, this is a dummy class!
    def generate_code(self, *args, **kwargs):
        pass
#
# The labscript device class
#
@labscript_device     
class CiceroOpalKellyXEM3001(PseudoclockDevice):
    # note: most parameters set in __init__ as they depend on reference clock frequency
    description = 'CiceroOpalKellyXEM3001'
    trigger_edge_type = 'rising' 
    allowed_children = [CiceroOpalKellyXEM3001Pseudoclock, CiceroOpalKellyXEM3001DummyPseudoclock]
    
    # Determined by confirming that an instruction table that is 2049 long
    # does not output the last instruction
    max_instructions = 2048
    
    @set_passed_properties(property_names = {
        "connection_table_properties": ["reference_clock", "clock_frequency", "trigger_debounce_clock_ticks"],
        "device_properties": ["trigger_delay", "wait_delay"]}
        )    
    def __init__(self, name, trigger_device=None, trigger_connection=None, serial='', reference_clock='internal', clock_frequency=100e6, use_wait_monitor=False, trigger_debounce_clock_ticks=10):
        # set device properties based on clock frequency
        self.clock_limit = clock_frequency/2
        self.clock_resolution = 1/clock_frequency
        # We'll set this to be 2x the debounce count
        self.trigger_minimum_duration = 2*trigger_debounce_clock_ticks/clock_frequency
        # Todo: confirm this.
        #       It should only be 5 clock cycles + the debounce_clock_ticks
        #       as I think it takes 3 clock cycles to propagate to the state
        #       machine of the FPGA code (due to the three uses of the non-blocking <= verilog operator
        #       in the debounce code) and then another 2 cycles before the output goes high
        #       (one to move out of the wait for retrigger code and then one because the update of the
        #        output state is non-blocking)\
        #
        self.trigger_delay = (5+trigger_debounce_clock_ticks)/clock_frequency
        # Todo: confirm this
        #       I believe it is 1 clock cycle
        self.wait_delay = self.clock_resolution
        
        PseudoclockDevice.__init__(self, name, trigger_device, trigger_connection)
        self.BLACS_connection = serial
        
        if trigger_debounce_clock_ticks >= 2**16:
            raise LabscriptError('The %s %s trigger_debounce_clock_ticks parameter must be between 0 and 65535'%(self.description, self.name))
        
        # create Pseudoclock and clockline
        self._pseudoclock = CiceroOpalKellyXEM3001Pseudoclock('%s_pseudoclock'%name, self, 'clock') # possibly a better connection name than 'clock'?
        # Create the internal direct output clock_line
        self._clock_line = ClockLine('%s_clock_line'%name, self.pseudoclock, 'Clock Out')
        
        # Create internal devices for connecting to a wait monitor
        self.__wait_monitor_dummy_pseudoclock = CiceroOpalKellyXEM3001DummyPseudoclock('%s__dummy_wait_pseudoclock'%name, self, '_')
        self.__wait_monitor_dummy_clock_line = CiceroOpalKellyXEM3001DummyClockLine('%s__dummy_wait_clock_line'%name, self.__wait_monitor_dummy_pseudoclock, '_')
        self.__wait_monitor_intermediate_device = CiceroOpalKellyXEM3001DummyIntermediateDevice('%s_internal_wait_monitor_outputs'%name, self.__wait_monitor_dummy_clock_line)
        
        if use_wait_monitor:
            WaitMonitor('%s__wait_monitor'%name, self.internal_wait_monitor_outputs, 'internal', self.internal_wait_monitor_outputs, 'internal', self.internal_wait_monitor_outputs, 'internal')
        
    @property
    def internal_wait_monitor_outputs(self):
        return self.__wait_monitor_intermediate_device
    
    @property
    def pseudoclock(self):
        return self._pseudoclock
    
    # Note, not to be confused with Device.parent_clock_line which returns the parent ClockLine
    # This one gives the automatically created ClockLine object
    @property
    def clockline(self):
        return self._clock_line
    
    def add_device(self, device):
        if len(self.child_devices) < 2 and isinstance(device, Pseudoclock):
            PseudoclockDevice.add_device(self, device)            
        elif isinstance(device, Pseudoclock):
            raise LabscriptError('The %s %s automatically creates a Pseudoclock because it only supports one. '%(self.description, self.name) +
                                 'Instead of instantiating your own Pseudoclock object, please use the internal' +
                                 ' one stored in %s.pseudoclock'%self.name)
        else:
            raise LabscriptError('You have connected %s (class %s) to %s, but %s does not support children with that class.'%(device.name, device.__class__, self.name, self.name))
    
    def generate_code(self, hdf5_file):
        PseudoclockDevice.generate_code(self, hdf5_file)
        group = hdf5_file['devices'].create_group(self.name)   
        
        # compress clock instructions with the same period: This will
        # halve the number of instructions roughly, since the PineBlaster
        # does not have a 'slow clock':
        reduced_instructions = []
        current_wait_index = 0
        wait_table = sorted(compiler.wait_table)
        
        if not self.is_master_pseudoclock:
            reduced_instructions.append({'on': 0, 'off': ((self.trigger_edge_type=='rising') << 1) + 1, 'reps': 0})
                
        for instruction in self.pseudoclock.clock:
            if instruction == 'WAIT':
                # The following period and reps indicates a wait instruction
                wait_timeout = compiler.wait_table[wait_table[current_wait_index]][1]
                current_wait_index += 1
                
                # The actual wait instruction.
                # on_counts correspond to teh number of reference clock cycles
                # to wait for external trigger before auto-resuming. 
                # It overcounts by 1 here because the logic on the FPGA is different for the first reference clock cycle 
                # (you cannot resume until the after second reference clock cycle), so we subtract 1 off the on counts
                # so that it times-out after the correct number of samples
                reduced_instructions.append({'on': round(wait_timeout/self.clock_resolution)-1, 'off': ((self.trigger_edge_type=='rising') << 1) + 1, 'reps': 0})
                continue
            reps = instruction['reps']
            # period is in quantised units:
            periods = int(round(instruction['step']/self.clock_resolution))
            # Get the "high" half of the clock period
            on_period = int(periods/2)
            # Use the remainder to calculate the "off period" (allows slightly assymetric clock signals so to minimise timing errors)
            off_period = periods-on_period
            
            if reduced_instructions and reduced_instructions[-1]['on'] == on_period and reduced_instructions[-1]['off'] == off_period:
                reduced_instructions[-1]['reps'] += reps
            else:
                reduced_instructions.append({'on': on_period, 'off': off_period, 'reps': reps})
        
        if len(reduced_instructions) > self.max_instructions:
            raise LabscriptError("%s %s has too many instructions. It has %d and can only support %d"%(self.description, self.name, len(reduced_instructions), self.max_instructions))
            
        # Store these instructions to the h5 file:
        dtypes = [('on_period',np.int64),('off_period',np.int64),('reps',np.int64)]
        pulse_program = np.zeros(len(reduced_instructions),dtype=dtypes)
        for i, instruction in enumerate(reduced_instructions):
            pulse_program[i]['on_period'] = instruction['on']
            pulse_program[i]['off_period'] = instruction['off']
            pulse_program[i]['reps'] = instruction['reps']
        group.create_dataset('PULSE_PROGRAM', compression = config.compression, data=pulse_program)
        
        self.set_property('is_master_pseudoclock', self.is_master_pseudoclock, location='device_properties')
        self.set_property('stop_time', self.stop_time, location='device_properties')
        
        
 

@runviewer_parser
class RunviewerClass(object):
    def __init__(self, path, device):
        self.path = path
        self.name = device.name
        self.device = device
        
            
    def get_traces(self, add_trace, clock=None):
        if clock is not None:
            times, clock_value = clock[0], clock[1]
            clock_indices = np.where((clock_value[1:]-clock_value[:-1])==1)[0]+1
            # If initial clock value is 1, then this counts as a rising edge (clock should be 0 before experiment)
            # but this is not picked up by the above code. So we insert it!
            if clock_value[0] == 1:
                clock_indices = np.insert(clock_indices, 0, 0)
            clock_ticks = times[clock_indices]

        
            
        # get the pulse program
        with h5py.File(self.path, 'r') as f:
            pulse_program = f['devices/%s/PULSE_PROGRAM'%self.name][:]
            device_properties = labscript_utils.properties.get(f, self.name, 'device_properties')
            connection_table_properties = labscript_utils.properties.get(f, self.name, 'connection_table_properties')
        
        clock_frequency = connection_table_properties['clock_frequency']

        time = []
        states = []
        trigger_index = 0
        # t = 0 if clock is None else clock_ticks[trigger_index]+device_properties['trigger_delay']
        # trigger_index += 1
        t = 0
               
        for row in pulse_program:
            if row['reps'] == 0: # WAIT
                if clock is not None:
                    t = clock_ticks[trigger_index]+device_properties['trigger_delay']
                    trigger_index += 1
                else:
                    t += device_properties['wait_delay']
            else:    
                for i in range(row['reps']):
                    time.append(t)
                    states.append(1)
                    t += row['on_period']/clock_frequency
                    time.append(t)
                    states.append(0)
                    t += row['off_period']/clock_frequency
        
        clock = (np.array(time), np.array(states))
        
        clocklines_and_triggers = {}
        for pseudoclock_name, pseudoclock in self.device.child_list.items():
            for clock_line_name, clock_line in pseudoclock.child_list.items():
                if clock_line.parent_port == 'Clock Out':
                    clocklines_and_triggers[clock_line_name] = clock
                    add_trace(clock_line_name, clock, self.name, clock_line.parent_port)
            
        return clocklines_and_triggers

from blacs.tab_base_classes import Worker, define_state, Tab
from blacs.tab_base_classes import MODE_MANUAL, MODE_TRANSITION_TO_BUFFERED, MODE_TRANSITION_TO_MANUAL, MODE_BUFFERED  

from blacs.device_base_class import DeviceTab

from qtutils.qt.QtCore import *
from qtutils.qt.QtGui import *
from qtutils.qt.QtWidgets import *

@BLACS_tab
class CiceroOpalKellyXEM3001Tab(DeviceTab):
    
    def initialise_GUI(self):
        # A variable to store whether the flash has filed. This will
        # inform the get_save_data() method as to whether to report the 
        # current reference clock configuration of the FPGA firmware
        self.failed_to_flash = False
    
        # Store the board number to be used
        connection_object = self.settings['connection_table'].find_by_name(self.device_name)
        self.serial = str(connection_object.BLACS_connection)
        self.reference_clock = connection_object.properties.get('reference_clock', 'internal')
        self.logger.debug('reference clock scheme is: %s'%self.reference_clock)
        # Create and set the primary worker
        self.create_worker("main_worker", CiceroOpalKellyXEM3001Worker, {'serial':self.serial, "reference_clock":self.reference_clock})
        self.primary_worker = "main_worker"
        
        # Set the capabilities of this device
        self.supports_smart_programming(False) 
        
        # Add button to force reflash
        self.flash_fpga_button = QPushButton('Flash FPGA firmware (this should be handled automatically by BLACS, if the device is not working correctly, try this button!)')
        self.flash_fpga_button.clicked.connect(self.flash_fpga)
        self.get_tab_layout().insertWidget(self.get_tab_layout().count()-1, self.flash_fpga_button)
        
     
    def get_child_from_connection_table(self, parent_device_name, port):
        # This is a direct output, let's search for it on the internal Pseudoclock
        if parent_device_name == self.device_name:
            device = self.connection_table.find_by_name(self.device_name)
            pseudoclock = device.child_list[list(device.child_list.keys())[0]] # there should always be one (and only one) child, the Pseudoclock
            clockline = None
            for child_name, child in pseudoclock.child_list.items():
                # store a reference to the internal clockline
                if child.parent_port == port:                
                    return DeviceTab.get_child_from_connection_table(self, pseudoclock.name, port)
            
        # If nothing found, Use default implementation
        return DeviceTab.get_child_from_connection_table(self, parent_device_name, port)
    
    def close_tab(self, *args, **kwargs):
        # disconnect method from button. This will allow the button to be garbage collected when it is shortly deleted
        self.flash_fpga_button.clicked.disconnect(self.flash_fpga)
        return Tab.close_tab(self, *args, **kwargs)
    
    def restore_save_data(self, data):
        # Flash the FPGA if the type of reference clock has changed since last time!
        if 'reference_clock' not in data or self.reference_clock != data['reference_clock']:
            self.flash_fpga()
    
    @define_state(MODE_MANUAL|MODE_BUFFERED|MODE_TRANSITION_TO_BUFFERED|MODE_TRANSITION_TO_MANUAL,True)
    def flash_fpga(self, ignore=None):
        ret = yield(self.queue_work(self.primary_worker, 'flash_FPGA'))
        if not ret:
            self.failed_to_flash = True
    
    def get_save_data(self):
        ret_data = {}
        # ignore the current reference clock configuration if we failed
        # to flash this time.
        # Note this will force a reflash next time the device is initialised
        if not self.failed_to_flash:
            ret_data['reference_clock'] = self.reference_clock
        return ret_data
     
    @define_state(MODE_BUFFERED|MODE_MANUAL,True)  
    def status_monitor(self, notify_queue):
        # remove the timeout if we are in manual mode (which happens when 
        # the abort button is clicked in BLACS)
        if self.mode == MODE_MANUAL:
            self.statemachine_timeout_remove(self.status_monitor)
            return
    
        status = yield(self.queue_work(self.primary_worker, 'status_monitor'))        
        if status:
            # Experiment is over. Tell the queue manager about it
            notify_queue.put('done')
            self.statemachine_timeout_remove(self.status_monitor)

        # handle exception in worker
        elif status is None:
            self.statemachine_timeout_remove(self.status_monitor)

            # TODO: This is a bit of a hack.
            # We fake a restart in order to notify the queue that something went wrong
            # and that it should abort the shot
            for f in self._restart_receiver:
                try:
                    f(self.device_name)
                except:
                    self.logger.exception('Could not notify a connected receiver function')
        
    @define_state(MODE_BUFFERED,True)  
    def start_run(self, notify_queue):
        """Starts the CiceroOpalKellyXEM3001, notifying the queue manager when
        the run is over"""
        # TODO: This 100ms (+ overhead) limits the minimum time you can have between 2 consecutive wait commands in labscript. Anything faster than this will not be detected properly.
        self.statemachine_timeout_add(100, self.status_monitor, notify_queue)
        yield(self.queue_work(self.primary_worker, 'start_run'))


@BLACS_worker        
class CiceroOpalKellyXEM3001Worker(Worker):
    def init(self):
        global h5py; import labscript_utils.h5_lock, h5py
        # global serial; import serial
        global time; import time
        global zprocess; import zprocess
        global ok; import ok # OpalKelly library

        # check the import worked correctly
        # This handles the difference between v4 and v5 of front panel I think
        if not hasattr(ok, 'okCFrontPanel'):
            from ok import ok

        global numpy; import numpy
    
        self.all_waits_finished = zprocess.Event('all_waits_finished',type='post')
        self.wait_durations_analysed = zprocess.Event('wait_durations_analysed',type='post')
        self.wait_completed = zprocess.Event('wait_completed', type='post')
        self.current_wait = 0
        self.wait_table = None
        self.measured_waits = None
        self.h5_file = None
    
        self.current_value = 0
    
        # Initialise connection to OPAL KELLY Board
        self.dev = ok.okCFrontPanel()
        assert self.dev.OpenBySerial(self.serial) == self.dev.NoError
        
        try:
            assert self.dev.IsFrontPanelEnabled()
        except AssertionError:
            # Flash the FPGA bit file
            self.flash_FPGA()
            
        # ensure the FPGA's state machine is deactivated
        assert self.dev.ActivateTriggerIn(0x40, 1) == self.dev.NoError
    
    def flash_FPGA(self):
        import os
        if self.reference_clock == 'internal':
            fpga_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),'CiceroOpalKellyXEM3001_fpga_internal.bit')
        elif self.reference_clock == 'external':
            fpga_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),'CiceroOpalKellyXEM3001_fpga_external.bit')
        else:
            raise RuntimeError('The reference_clock argument of the labscript class must be set to "internal" or "external". It is currently set to "%s"'%self.reference_clock)
            
        # explicitly raise an exception if the path doesn't exist because apparent the dev.ConfigureFPGA() method doesn't raise an error if the file is missing
        if not os.path.exists(fpga_path):
            raise RuntimeError('Cannot flash the FPGA for the current reference clock configuration as the .bit file is missing. Please ensure the correct bit file is available at %s'%fpga_path)
            
        self.logger.debug('Flashing FPGA bit file located at: %s'%fpga_path)
        self.dev.ConfigureFPGA(fpga_path)
        assert self.dev.IsFrontPanelEnabled(), 'Flashing of the FPGA failed. The device is not configured with the .bit file correctly'

        
        return True
    
    def shutdown(self):
		# signal the state machine to halt execution
        self.dev.ActivateTriggerIn(0x40, 1)
		# close the connection
        del self.dev	# close() function not available in Python
        
    # Dummy method because there is no manual mode for this device
    def program_manual(self, values):    
        return values
                
    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):
        self.h5_file = h5file # store reference to h5 file for wait monitor
        self.current_wait = 0 # reset wait analysis
        
        # Abort any manual mode loop (manual mode is a hack which has it stuck in a wait) and return the output to 0 in preparation for clock to begin
        self.abort()
        
        with h5py.File(h5file,'r') as hdf5_file:
            
            # main data
            group = hdf5_file['devices/%s'%device_name]
            pulse_program = group['PULSE_PROGRAM'][:]
            device_properties = labscript_utils.properties.get(hdf5_file, device_name, 'device_properties')
            self.connection_table_properties = labscript_utils.properties.get(hdf5_file, device_name, 'connection_table_properties')
            self.is_master_pseudoclock = device_properties['is_master_pseudoclock']
            
            # waits            
            dataset = hdf5_file['waits']
            acquisition_device = dataset.attrs['wait_monitor_acquisition_device']
            timeout_device = dataset.attrs['wait_monitor_timeout_device']
            if len(dataset) > 0 and acquisition_device == '%s_internal_wait_monitor_outputs'%device_name and timeout_device == '%s_internal_wait_monitor_outputs'%device_name:      
                self.wait_table = dataset[:]
                self.measured_waits = numpy.zeros(len(self.wait_table))
            else:
                self.wait_table = None # This device doesn't need to worry about looking at waits
                self.measured_waits = None
                
        # set debounce counter
        self.dev.SetWireInValue(0x01, self.connection_table_properties['trigger_debounce_clock_ticks'])
        self.dev.UpdateWireIns()
        
        # consistency check
        if self.wait_table is not None and not self.is_master_pseudoclock:
            raise RuntimeError('Something has gone wrong in labscript. You should not be able to configure this device as the wait monitor while it is a secondary pseudoclock. Please contact the developers on the mailing list.')
                
        # Create empty data array
        data = bytearray(len(pulse_program)*16)
        for i, instruction in enumerate(pulse_program):
            add_instruction_to_bytearray(data, i, instruction['on_period'], instruction['off_period'], instruction['reps'])
        
        # program the FPGA
        assert self.dev.WriteToPipeIn(0x80, data) == len(data)

        # If not the master pseudoclock, then we need to start the device
        # now so that the internal state machine can hit the first wait 
        # instruction and be prepared to output on the first trigger
        if not self.is_master_pseudoclock:
            self.start_run()
        
        return {'Clock Out':0} # always finish on 0
            
    def start_run(self):
        # Start in software:
        assert self.dev.ActivateTriggerIn(0x40,0) == self.dev.NoError
    
    def status_monitor(self):
        def ReadU32(addr):
            lo = self.dev.GetWireOutValue(addr)
            hi = self.dev.GetWireOutValue(addr+1)
            vx = (hi << 16) | lo
            return vx
        
        # update the status monitors
        self.dev.UpdateWireOuts()
                
        #   WAIT ANALYSIS CODE: 
        #       If this device has a wait monitor attached
        #       Read wires 22+23 (masterSamplesGenerated)
        #                  24 (retriggerTimeoutCount)
        #                  26+27 (retriggerWaitSamples)
        #
        #       find out if this device was the wait monitor by looking at 
        #       hdf5_file['waits'].attrs['wait_monitor_acquisition_device']
        #       and hdf5_file['waits'].attrs['wait_monitor_timeout_device']
        #
        #       To determine the length of waits. Note this is a bit tricky 
        #       because if waits are close we might miss one (cicero must have
        #       the same problem). You also need to reverse engineer the 
        #       of the wait from the retriggerWaitSamples which appears to be
        #       a cumulative total of wait samples. You could use 
        #       masterSamplesGenerated to work out which wait just happened
        #       based on the clock_resolution and the wait time in the 
        #       "waits" table of the HDF5 file.
        #       
        #       send ZMQ all_waits_finished event when all waits have happened.
        #       self.all_waits_finished.post(self.h5_file)
        if self.wait_table is not None and self.current_wait < len(self.wait_table):
            # master_samples_generated_1 = self.dev.GetWireOutValue(0x22)
            # master_samples_generated_2 = self.dev.GetWireOutValue(0x23)
            # master_samples_generated = (master_samples_generated_2 << 16) + master_samples_generated_1
            
            master_samples_generated = bits_to_int(16, self.dev.GetWireOutValue(0x22), self.dev.GetWireOutValue(0x23))
            self.logger.debug('Master samples generated: %d'%master_samples_generated)
        
            clock_frequency = self.connection_table_properties['clock_frequency']

            # find time of current wait
            wait_sample = int(self.wait_table[self.current_wait][1]*clock_frequency)
            # for some reason this needs to be incremented by 1?
            #wait_sample += 1
            self.logger.debug('Wait sample: %d'%wait_sample)
            if wait_sample < master_samples_generated:
                # a wait has happened!
                # let's make sure 2 waits have not happened before we noticed the first...
                if len(self.wait_table) > self.current_wait+1:
                    next_wait_sample = int(self.wait_table[self.current_wait+1][1]*clock_frequency)
                    assert next_wait_sample > master_samples_generated, 'Error: a wait happened too soon after another wait to determine the length of each wait individually.'
                
                # work out the length of the last wait
                retrigger_wait_samples = bits_to_int(16, self.dev.GetWireOutValue(0x26), self.dev.GetWireOutValue(0x27))
                self.logger.debug('Retrigger wait samples: %d'%retrigger_wait_samples)
                # store length of wait (must be stored in clock samples so that
                # we can subtract off this number of samples for a following wait)
                self.measured_waits[self.current_wait] = retrigger_wait_samples-self.measured_waits.sum()

                # Inform any interested parties that a wait has completed:
                self.wait_completed.post(self.h5_file, data=_ensure_str(self.wait_table[self.current_wait]['label']))

                # increment the wait we are looking for!
                self.current_wait += 1
                
                # post message if all waits are done
                if len(self.wait_table) == self.current_wait:
                    self.all_waits_finished.post(self.h5_file)
                
        # check the status bits
        status = self.dev.GetWireOutValue(0x25)
        assert not status & 2	# aborted
        return status & 1		# finished
        
    def transition_to_manual(self):
        #       Save wait data if there were waits and this was the wait monitor
        #       find out if this device was the wait monitor by looking at 
        #       hdf5_file['waits'].attrs['wait_monitor_acquisition_device']
        #       and hdf5_file['waits'].attrs['wait_monitor_timeout_device']
        #       
        #       write the table to hdf5_file['/data/waits']. Columns are:
        #           label: Same as hdf5_file['waits']['label']
        #           time: Same as hdf5_file['waits']['time']
        #           timeout: Same as hdf5_file['waits']['timeout']
        #           duration: duration of the wait in seconds
        #           timed_out: Boolean indicating if the wait timed out
        #
        #       Send ZMQ wait_durations_analysed event when the table has been
        #       written
        #       self.wait_durations_analysed.post(self.h5_file)
    
        clock_frequency = self.connection_table_properties['clock_frequency']

        if self.wait_table is not None:
            with h5py.File(self.h5_file,'a') as hdf5_file:
                # Work out how long the waits were, save em, post an event saying so 
                dtypes = [('label','a256'),('time',float),('timeout',float),('duration',float),('timed_out',bool)]
                data = numpy.empty(len(self.wait_table), dtype=dtypes)
                data['label'] = self.wait_table['label']
                data['time'] = self.wait_table['time']
                data['timeout'] = self.wait_table['timeout']
                # convert to seconds
                data['duration'] = self.measured_waits/clock_frequency
                data['timed_out'] = data['duration'] >= data['timeout']
            
                hdf5_file.create_dataset('/data/waits', data=data)
        
            self.wait_durations_analysed.post(self.h5_file)
        
        return True
    
    def abort_buffered(self):
        return self.abort()
    
    def abort_transition_to_buffered(self):
        return self.abort()
    
    def abort(self):
        # Send abort signal on wire soft_abort_trig_in
        assert self.dev.ActivateTriggerIn(0x40,1) == self.dev.NoError
        # NB: the state machine must notice first
        
        # update the locally stored current value flag (used in manual mode)
        self.current_value = 0
        
        # Read status of OPAL KELLY BOARD
        self.dev.UpdateWireOuts()
        return self.dev.GetWireOutValue(0x25) & 2

