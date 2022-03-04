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


class WindfreakSynthWorker(Worker):

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
        # set trigger mode from connection_table_properties
        self.set_trigger_mode(self.trigger_mode)

        # populate smart chache
        self.smart_cache['STATIC_DATA'] = self.check_remote_values()

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

    def check_remote_value(self,channel,type):

        if type == 'freq':
            return self.synth[channel].frequency
        elif type == 'amp':
            return self.synth[channel].power
        elif type == 'phase':
            return self.synth[channel].phase
        elif type == 'gate':
            return self.synth[channel].rf_enable and self.synth[channel].pll_enable
        else:
            raise ValueError(type)

    def program_static_value(self,channel,type,value):

        if type == 'freq':
            self.synth[channel].frequency = value
        elif type == 'amp':
            self.synth[channel].power = value
        elif type == 'phase':
            self.synth[channel].phase = value
        elif type == 'gate':
            self.synth[channel].rf_enable = value
            self.synth[channel].pll_enable = value
        else:
            raise ValueError(type)

    def transition_to_buffered(self, device_name, h5file, initial_values, fresh):

        self.initial_values = initial_values
        self.final_values = initial_values

        static_data = None
        with h5py.File(h5file,'r') as hdf5_file:
            group = hdf5_file['/devices/'+device_name]
            if 'STATIC_DATA' in group:
                static_data = group['STATIC_DATA'][:][0]

        if static_data is not None:
            data = static_data
            if fresh or data != self.smart_cache['STATIC_DATA']:

                # need to infer which channels are programming
                num_chan = len(data)//len(self.subchnls)
                channels = [int(name[-1]) for name in data.dtype.names[0:num_chan]]

                for i in channels:
                    for sub in self.subchnls:
                        self.program_static_value(i,sub,data[sub+str(i)])

                # update smart cache to reflect programmed values
                self.smart_cache['STATIC_DATA'] = data


        return self.final_values

    def shutdown(self):
        # save current state the memory
        self.synth.save()
        self.synth.close()