#####################################################################
#                                                                   #
# /PineBlaster.py                                                   #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################

from labscript import PseudoclockDevice, Pseudoclock, ClockLine, config, LabscriptError, set_passed_properties
from labscript_devices import runviewer_parser, BLACS_tab

import numpy as np
import labscript_utils.h5_lock, h5py
import labscript_utils.properties



# Define a PineBlasterPseudoClock that only accepts one child clockline
class PineBlasterPseudoclock(Pseudoclock):    
    def add_device(self, device):
        if isinstance(device, ClockLine):
            # only allow one child
            if self.child_devices:
                raise LabscriptError('The pseudoclock of the PineBlaster %s only supports 1 clockline, which is automatically created. Please use the clockline located at %s.clockline'%(self.parent_device.name, self.parent_device.name))
            Pseudoclock.add_device(self, device)
        else:
            raise LabscriptError('You have connected %s to %s (the Pseudoclock of %s), but %s only supports children that are ClockLines. Please connect your device to %s.clockline instead.'%(device.name, self.name, self.parent_device.name, self.name, self.parent_device.name))


class PineBlaster(PseudoclockDevice):
    description = 'PineBlaster'
    clock_limit = 10e6
    clock_resolution = 25e-9
    clock_type = 'fast clock'
    # Measured by Phil Starkey on 2015/9/24
    trigger_delay = 350e-9
    # Todo: find out what this actually is:
    wait_delay = 2.5e-6
    allowed_children = [PineBlasterPseudoclock]
    
    max_instructions = 15000
    
    @set_passed_properties(property_names = {
        "connection_table_properties": ["usbport"]}
        )    
    def __init__(self, name, trigger_device=None, trigger_connection=None, usbport='COM1'):
        PseudoclockDevice.__init__(self, name, trigger_device, trigger_connection)
        self.BLACS_connection = usbport
        
        # create Pseudoclock and clockline
        self._pseudoclock = PineBlasterPseudoclock('%s_pseudoclock'%name, self, 'clock') # possibly a better connection name than 'clock'?
        # Create the internal direct output clock_line
        self._clock_line = ClockLine('%s_clock_line'%name, self.pseudoclock, 'internal')
    
    @property
    def pseudoclock(self):
        return self._pseudoclock
    
    # Note, not to be confused with Device.parent_clock_line which returns the parent ClockLine
    # This one gives the automatically created ClockLine object
    @property
    def clockline(self):
        return self._clock_line
    
    def add_device(self, device):
        if not self.child_devices and isinstance(device, Pseudoclock):
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
        for instruction in self.pseudoclock.clock:
            if instruction == 'WAIT':
                # The following period and reps indicates a wait instruction
                reduced_instructions.append({'period': 0, 'reps': 1})
                continue
            reps = instruction['reps']
            # period is in quantised units:
            period = int(round(instruction['step']/self.clock_resolution))
            if reduced_instructions and reduced_instructions[-1]['period'] == period:
                reduced_instructions[-1]['reps'] += reps
            else:
                reduced_instructions.append({'period': period, 'reps': reps})
        # The following period and reps indicates a stop instruction:
        reduced_instructions.append({'period': 0, 'reps': 0})
        if len(reduced_instructions) > self.max_instructions:
            raise LabscriptError("%s %s has too many instructions. It has %d and can only support %d"%(self.description, self.name, len(reduced_instructions), self.max_instructions))
        # Store these instructions to the h5 file:
        dtypes = [('period',int),('reps',int)]
        pulse_program = np.zeros(len(reduced_instructions),dtype=dtypes)
        for i, instruction in enumerate(reduced_instructions):
            pulse_program[i]['period'] = instruction['period']
            pulse_program[i]['reps'] = instruction['reps']
        group.create_dataset('PULSE_PROGRAM', compression = config.compression, data=pulse_program)
        # TODO: is this needed, the PulseBlasters don't save it... 
        self.set_property('is_master_pseudoclock', self.is_master_pseudoclock, location='device_properties')
        self.set_property('stop_time', self.stop_time, location='device_properties')
 

@runviewer_parser
class RunviewerClass(object):
    clock_resolution = 25e-9
    clock_type = 'fast clock'
    # Todo: find out what this actually is:
    trigger_delay = 1e-6
    # Todo: find out what this actually is:
    wait_delay = 2.5e-6
    
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
            
        time = []
        states = []
        trigger_index = 0
        t = 0 if clock is None else clock_ticks[trigger_index]+self.trigger_delay
        trigger_index += 1
        
        clock_factor = self.clock_resolution/2.
        
        for row in pulse_program:
            if row['period'] == 0:
                #special case
                if row['reps'] == 1: # WAIT
                    if clock is not None:
                        t = clock_ticks[trigger_index]+self.trigger_delay
                        trigger_index += 1
                    else:
                        t += self.wait_delay
            else:    
                for i in range(row['reps']):
                    for j in range(1, -1, -1):
                        time.append(t)
                        states.append(j)
                        t += row['period']*clock_factor
        
        clock = (np.array(time), np.array(states))
        
        clocklines_and_triggers = {}
        for pseudoclock_name, pseudoclock in self.device.child_list.items():
            for clock_line_name, clock_line in pseudoclock.child_list.items():
                if clock_line.parent_port == 'internal':
                    clocklines_and_triggers[clock_line_name] = clock
                    add_trace(clock_line_name, clock, self.name, clock_line.parent_port)
            
        return clocklines_and_triggers

from blacs.tab_base_classes import Worker, define_state
from blacs.tab_base_classes import MODE_MANUAL, MODE_TRANSITION_TO_BUFFERED, MODE_TRANSITION_TO_MANUAL, MODE_BUFFERED  

from blacs.device_base_class import DeviceTab

@BLACS_tab
class PineblasterTab(DeviceTab):
    
    def initialise_GUI(self):
        # Create a single digital output     
        self.create_digital_outputs({'internal':{}})        
        # Create widgets for output objects
        _,_,do_widgets = self.auto_create_widgets()
        # and auto place the widgets in the UI
        self.auto_place_widgets(("Flags", do_widgets))
        
        # Store the board number to be used
        self.usb_port = str(self.settings['connection_table'].find_by_name(self.device_name).BLACS_connection)
        # Create and set the primary worker
        self.create_worker("main_worker", PineblasterWorker, {'usbport':self.usb_port})
        self.primary_worker = "main_worker"
        
        # Set the capabilities of this device
        self.supports_smart_programming(True) 
     
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
            
        return '-'
        
     
    @define_state(MODE_BUFFERED,True)  
    def status_monitor(self, notify_queue):
        status = yield(self.queue_work(self.primary_worker, 'status_monitor'))        
        if status:
            # Experiment is over. Tell the queue manager about it
            notify_queue.put('done')
            self.statemachine_timeout_remove(self.status_monitor)
        
    @define_state(MODE_BUFFERED,True)  
    def start_run(self, notify_queue):
        """Starts the Pineblaster, notifying the queue manager when
        the run is over"""
        self.statemachine_timeout_add(100, self.status_monitor, notify_queue)
        yield(self.queue_work(self.primary_worker, 'start_run'))


class PineblasterWorker(Worker):
    def init(self):
        global h5py; import labscript_utils.h5_lock, h5py
        global serial; import serial
        global time; import time
        self.smart_cache = []
    
        self.pineblaster = serial.Serial(self.usbport, 115200, timeout=1)
        # Device has a finite startup time:
        time.sleep(5)
        self.pineblaster.write(b'hello\r\n')
        response = self.pineblaster.readline().decode()
        
        if response == 'hello\r\n':
            return
        elif response:
            raise Exception('PineBlaster is confused: saying %s instead of hello'%(repr(response)))
        else:
            raise Exception('PineBlaster is not saying hello back when greeted politely. How rude. Maybe it needs a reboot.')
            
            
    def shutdown(self):
        self.pineblaster.close()
        
    def program_manual(self, values):    
        value = values['internal'] # there is only one value
        self.pineblaster.write(b'go high\r\n' if value else b'go low\r\n')
        response = self.pineblaster.readline().decode()
        assert response == 'ok\r\n', 'PineBlaster said \'%s\', expected \'ok\''%repr(response)
        return {}
        
    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):
        if fresh:
            self.smart_cache = []
        self.program_manual({'internal':0})
        
        with h5py.File(h5file,'r') as hdf5_file:
            group = hdf5_file['devices/%s'%device_name]
            pulse_program = group['PULSE_PROGRAM'][:]
            device_properties = labscript_utils.properties.get(hdf5_file, device_name, 'device_properties')
            self.is_master_pseudoclock = device_properties['is_master_pseudoclock']
            
        for i, instruction in enumerate(pulse_program):
            if i == len(self.smart_cache):
                # Pad the smart cache out to be as long as the program:
                self.smart_cache.append(None)
                
            # Only program instructions that differ from what's in the smart cache:
            if self.smart_cache[i] != instruction:
                self.pineblaster.write(b'set %d %d %d\r\n'%(i, instruction['period'], instruction['reps']))
                response = self.pineblaster.readline().decode()
                assert response == 'ok\r\n', 'PineBlaster said \'%s\', expected \'ok\''%repr(response)
                self.smart_cache[i] = instruction
                
        if not self.is_master_pseudoclock:
            # Get ready for a hardware trigger:
            self.pineblaster.write(b'hwstart\r\n')
            response = self.pineblaster.readline().decode()
            assert response == 'ok\r\n', 'PineBlaster said \'%s\', expected \'ok\''%repr(response)
            
        return {'internal':0} # always finish on 0
            
    def start_run(self):
        # Start in software:
        self.pineblaster.write(b'start\r\n')
        response = self.pineblaster.readline().decode()
        assert response == 'ok\r\n', 'PineBlaster said \'%s\', expected \'ok\''%repr(response)
    
    def status_monitor(self):
        # Wait to see if it's done within the timeout:
        response = self.pineblaster.readline().decode()
        if response:
            assert response == 'done\r\n'
            return True
        return False
        
    def transition_to_manual(self):
        # Wait until the pineblaster says it's done:
        if not self.is_master_pseudoclock:
            # If we're the master pseudoclock then this already happened
            # in status_monitor, so we don't need to do it again
            response = self.pineblaster.readline().decode()
            assert response == 'done\r\n', 'PineBlaster said \'%s\', expected \'ok\''%repr(response)
            # print 'done!'
        return True
    
    def abort_buffered(self):
        return self.abort()
    
    def abort_transition_to_buffered(self):
        return self.abort()
    
    def abort(self):
        self.pineblaster.write(b'restart\r\n')
        time.sleep(5)
        self.shutdown()
        self.init()
        return True

