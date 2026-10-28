#####################################################################
#                                                                   #
# /labscript_devices/CiceroOpalKellyXEM3001/blacs_workers.py        #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################
import labscript_utils.properties
from labscript_utils.connections import _ensure_str
from blacs.tab_base_classes import Worker


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
    
        self.all_waits_finished = zprocess.Event('all_waits_finished',role='post')
        self.wait_durations_analysed = zprocess.Event('wait_durations_analysed',role='post')
        self.wait_completed = zprocess.Event('wait_completed', role='post')
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
            
        self.logger.debug('Flashing FPGA bit file located at: %s', fpga_path)
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
            self.logger.debug('Master samples generated: %d', master_samples_generated)
        
            clock_frequency = self.connection_table_properties['clock_frequency']

            # find time of current wait
            wait_sample = int(self.wait_table[self.current_wait][1]*clock_frequency)
            # for some reason this needs to be incremented by 1?
            #wait_sample += 1
            self.logger.debug('Wait sample: %d', wait_sample)
            if wait_sample < master_samples_generated:
                # a wait has happened!
                # let's make sure 2 waits have not happened before we noticed the first...
                if len(self.wait_table) > self.current_wait+1:
                    next_wait_sample = int(self.wait_table[self.current_wait+1][1]*clock_frequency)
                    assert next_wait_sample > master_samples_generated, 'Error: a wait happened too soon after another wait to determine the length of each wait individually.'
                
                # work out the length of the last wait
                retrigger_wait_samples = bits_to_int(16, self.dev.GetWireOutValue(0x26), self.dev.GetWireOutValue(0x27))
                self.logger.debug('Retrigger wait samples: %d', retrigger_wait_samples)
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
                dtypes = [('label','S256'),('time',float),('timeout',float),('duration',float),('timed_out',bool)]
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
