#####################################################################
#                                                                   #
# /labscript_devices/Windfreak/blacs_workers.py                     #
#                                                                   #
# Copyright 2022, Monash University and contributors                #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

from blacs.tab_base_classes import Worker
import labscript_utils.h5_lock, h5py
import numpy as np


class WindfreakSynthHDWorker(Worker):

    def init(self):
        # hide import of 3rd-party library in here so docs don't need it
        global windfreak; import windfreak

        # init smart cache to a known point
        self.smart_cache = {'STATIC_DATA':None}
        self.subchnls = ['freq','amp','phase','gate']
        # this will be the order in which each channel is programmed

        Worker.init(self)

        # connect to synth
        self.synth = windfreak.SynthHD(self.com_port)
        self.valid_modes = self.synth.trigger_modes
        self.valid_ref_modes = self.synth.reference_modes
        # set reference mode
        self.set_reference_mode(self.reference_mode, self.reference_frequency)
        # set trigger mode from connection_table_properties
        self.set_trigger_mode(self.trigger_mode)

        # populate smart chache
        self.smart_cache['STATIC_DATA'] = self.check_remote_values()

    def set_reference_mode(self, mode, ext_freq):
        """Sets the synth reference mode.
        
        Provides basic error checking that setting is valid.

        Args:
            mode (str): Valid reference modes are `external`, `internal 27mhz`
                and `internal 10mhz`. If mode is external, ext_freq must be provided.
            ext_freq (float): Frequency of external reference.
                If using internal reference, pass `None`.

        Raises:
            ValueError: if `mode` is not a valid setting or `ext_ref` not provided
                when using an external reference.
        """

        if mode == 'external' and ext_freq is None:
            raise ValueError('Must specify external reference frequency')

        if mode in self.valid_ref_modes:
            self.synth.reference_mode = mode
            if mode == 'external':
                self.synth.reference_frequency = ext_freq
        else:
            raise ValueError(f'{mode} not in {self.valid_ref_modes}')

    def set_trigger_mode(self,mode):
        """Sets the synth trigger mode.

        Provides basic error checking to confirm setting is valid.

        Args:
            mode (str): Trigger mode to set.

        Raises:
            ValueError: If `mode` is not a valid setting for the device.
        """

        if mode in self.valid_modes:
            self.synth.trigger_mode = mode
        else:
            raise ValueError(f'{mode} not in {self.valid_modes}')

    def check_remote_values(self):

        results = {}
        for i in self.allowed_chans:
            chan = f'channel {i:d}'
            results[chan] = {}
            for sub in self.subchnls:
                results[chan][sub] = self.check_remote_value(i,sub)

        return results

    def program_manual(self, front_panel_values):

        for i in self.allowed_chans:
            chan = f'channel {i:d}'
            for sub in self.subchnls:
                if self.smart_cache['STATIC_DATA'][chan][sub] == front_panel_values[chan][sub]:
                    # don't program if desired setting already present
                    continue
                self.program_static_value(i,sub,front_panel_values[chan][sub])
                # invalidate smart cache upon manual programming
                self.smart_cache['STATIC_DATA'][chan][sub] = None

        return self.check_remote_values()

    def check_remote_value(self,channel,typ):
        """Checks the remote value of a parameter for a channel.
        
        Args:
            channel (int): Which channel to check. Must be 0 or 1.
            typ (str): Which parameter to get. Must be `freq`, `amp`, `phase`
                or `gate`.

        Raises:
            ValueError: If `typ` is not a valid parameter type for the channel.
        """

        if typ == 'freq':
            return self.synth[channel].frequency
        elif typ == 'amp':
            return self.synth[channel].power
        elif typ == 'phase':
            return self.synth[channel].phase
        elif typ == 'gate':
            return self.synth[channel].rf_enable and self.synth[channel].pll_enable
        else:
            raise ValueError(typ)

    def program_static_value(self,channel,typ,value):
        """Program a value for the specified parameter of the channel.
        
        Args:
            channel (int): Channel to program. Must be 0 or 1.
            typ (str): Parameter to program. Must be `freq`, `amp`, `phase`,
                or `gate`.
            value (float or bool): Value to program. `gate` takes a boolean type,
                all others take a float.

        Raises:
            ValueError: If requested parameter type is not valid.
        """

        if typ == 'freq':
            self.synth[channel].frequency = value
        elif typ == 'amp':
            self.synth[channel].power = value
        elif typ == 'phase':
            self.synth[channel].phase = value
        elif typ == 'gate':
            # windfreak API does not like np.bool_
            # convert to native python bool
            if isinstance(value, np.bool_):
                value = value.item()
            self.synth[channel].rf_enable = value
            self.synth[channel].pll_enable = value
        else:
            raise ValueError(typ)

    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):

        self.initial_values = initial_values
        self.final_values = initial_values

        static_data = None
        with h5py.File(h5file,'r') as hdf5_file:
            group = hdf5_file['/devices/'+device_name]
            if 'STATIC_DATA' in group:
                static_data = group['STATIC_DATA'][:][0]

        if static_data is not None:

            # need to infer which channels are programming
            num_chan = len(static_data)//len(self.subchnls)
            channels = [int(name[-1]) for name in static_data.dtype.names[0:num_chan]]

            for i in channels:
                for sub in self.subchnls:
                    desired_value = static_data[sub+str(i)]
                    if self.smart_cache['STATIC_DATA'][f'channel {i:d}'][sub] != desired_value or fresh:
                        self.program_static_value(i,sub,desired_value)
                        # update smart cache to reflect programmed values
                        self.smart_cache['STATIC_DATA'][f'channel {i:d}'][sub] = desired_value
                        # update final values to reflect programmed values
                        self.final_values[f'channel {i:d}'][sub] = desired_value

        return self.final_values

    def shutdown(self):
        # save current state the memory
        self.synth.save()
        self.synth.close()

    def abort_transition_to_buffered(self):
        """Special abort shot configuration code belongs here.
        """
        return self.transition_to_manual(True)
        
    def abort_buffered(self):
        """Special abort shot code belongs here.
        """
        return self.transition_to_manual(True)
            
    def transition_to_manual(self,abort = False):
        """Simple transition_to_manual method where no data is saved."""         
        if abort:
            # If we're aborting the run, reset to original value
            self.program_manual(self.initial_values)
        # If we're not aborting the run, stick with buffered value. Nothing to do really!

        return True
