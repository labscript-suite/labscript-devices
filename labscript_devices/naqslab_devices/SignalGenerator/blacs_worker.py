#####################################################################
#                                                                   #
# /naqslab_devices/SignalGenerator/blacs_worker.py                  #
#                                                                   #
# Copyright 2018, David Meyer                                       #
#                                                                   #
# This file is part of the naqslab devices extension to the         #
# labscript_suite. It is licensed under the Simplified BSD License. #
#                                                                   #
#                                                                   #
#####################################################################
import numpy as np

from naqslab_devices.VISA.blacs_worker import VISAWorker
from labscript import LabscriptError 

import labscript_utils.h5_lock, h5py

# note, when adding a new model, put the labscript_device inheritor class
# into Models.py and the BLACS classes into a file named for the device
# in the BLACS subfolder. Update register_classes.py and __init__.py
# accordingly.


class enable_on_off_formatter(str):
    '''Class overload that converts input bools to ON or OFF string'''

    def format(self, state):
        if state == 0:
            s = 'OFF'
        elif state == 1:
            s = 'ON'
        else:
            raise ValueError('Argument must be 0 or 1 equivalent.')

        return super().format(s)


class SignalGeneratorWorker(VISAWorker):    

    # define instrument specific read and write strings for Freq & Amp control
    freq_write_string = ''
    freq_query_string = ''
    def freq_parser(self,freq_string):
        '''Frequency Query string parser

        Converts string to float; should be be over-ridden
        if that is insufficient.

        Args:
            freq_string (str): String result from query.

        Returns:
            float: Frequency as a float.
        '''
        freq = float(freq_string)
        return freq
    amp_write_string = ''
    amp_query_string = ''
    def amp_parser(self,amp_string):
        '''Amplitude Query string parser

        Converts string to float; should be be over-ridden
        if that is insufficient.

        Args:
            amp_string (str): String result from query.

        Returns:
            float: Amplitude as a float.
        '''
        amp = float(amp_string)
        return amp
    enable_write_string = ''
    enable_query_string = ''
    def enable_parser(self,enable_string):
        '''Output Enable Query string parser.

        Converts the string to bool; should be over-ridden
        if that is insufficient.

        Args:
            enable_string (str): String result from query.

        Returns:
            bool: Boolean that indicates if output is enabled or not.
        '''
        enable = bool(int(enable_string))
        return enable
    
    def update_cache_from_dict(self, front_panel):
        '''Update the STATIC smart cache from a front_panel dictionary'''

        for chan, d in front_panel.items():
            chan_n = chan.split(' ')[-1]
            self.smart_cache['STATIC_DATA']['freq'+chan_n] = d['freq']*self.scale_factor
            self.smart_cache['STATIC_DATA']['amp'+chan_n] = d['amp']*self.amp_scale_factor
            self.smart_cache['STATIC_DATA']['gate'+chan_n] = d['gate']

    def init(self):
        # Call the VISA init to initialise the VISA connection
        VISAWorker.init(self)

        # initialize the smart cache
        static_dtypes = np.dtype({'names':['freq0','amp0','gate0'],
                                  'formats':[np.uint64,np.float16,bool]})
        self.smart_cache = {'STATIC_DATA': np.zeros(1, dtype=static_dtypes)[0]}

        # set static smart cache to current state
        current_state = self.check_remote_values()
        self.update_cache_from_dict(current_state)

    def check_remote_values(self):
        # Get the currently output values:

        results = {'channel 0':{}}

        # these query strings and parsers depend heavily on device
        freq = self.connection.query(self.freq_query_string)
        amp = self.connection.query(self.amp_query_string)
        enable = self.connection.query(self.enable_query_string)

        # Convert string to MHz:
        results['channel 0']['freq'] = self.freq_parser(freq)/self.scale_factor

        results['channel 0']['amp'] = self.amp_parser(amp)/self.amp_scale_factor

        results['channel 0']['gate'] = self.enable_parser(enable)

        return results

    def program_manual(self,front_panel_values):
        freq = front_panel_values['channel 0']['freq']
        amp = front_panel_values['channel 0']['amp']
        enable = front_panel_values['channel 0']['gate']

        # program with scale factor
        fcommand = self.freq_write_string.format(freq*self.scale_factor)
        self.connection.write(fcommand)

        # program with scale factor
        acommand = self.amp_write_string.format(amp*self.amp_scale_factor)
        self.connection.write(acommand)

        # set output state
        ecommand = self.enable_write_string.format(enable)
        self.connection.write(ecommand)

        # update smart_cache after manual update
        updated_state = self.check_remote_values()
        self.update_cache_from_dict(updated_state)

        return self.check_remote_values()

    def transition_to_buffered(self,device_name,h5file,initial_values,fresh):
        # call parent method to do basic preamble
        VISAWorker.transition_to_buffered(self,device_name,h5file,initial_values,fresh)
        data = None
        # Program static values
        with h5py.File(h5file,'r') as hdf5_file:
            group = hdf5_file['/devices/'+device_name]
            # If there are values to set the unbuffered outputs to, set them now:
            if 'STATIC_DATA' in group:
                data = group['STATIC_DATA'][0]

        if data is not None:

            if fresh or data != self.smart_cache['STATIC_DATA']:

                # program freq and amplitude as necessary
                if data['freq0'] != self.smart_cache['STATIC_DATA']['freq0']:
                    self.connection.write(self.freq_write_string.format(data['freq0']))
                if data['amp0'] != self.smart_cache['STATIC_DATA']['amp0']:
                    self.connection.write(self.amp_write_string.format(data['amp0']))
                if data['gate0'] != self.smart_cache['STATIC_DATA']['gate0']:
                    self.connection.write(self.enable_write_string.format(data['gate0']))

                # update smart_cache
                self.smart_cache['STATIC_DATA'] = data

                # Save these values into final_values so the GUI can
                # be updated at the end of the run to reflect them:
                final_values = {'channel 0':{}}

                final_values['channel 0']['freq'] = data['freq0']/self.scale_factor
                final_values['channel 0']['amp'] = data['amp0']/self.amp_scale_factor
                final_values['channel 0']['gate'] = data['gate0']

            else:
                final_values = self.initial_values

        return final_values


class MockSignalGeneratorWorker(SignalGeneratorWorker):
    """Mock Signal Generator Class

    Mock class for testing Signal Generator Tab functionality.
    It does not communicate with any hardware.
    """

    def init(self):
        # initialize the smart cache
        self.smart_cache = {'STATIC_DATA': {'freq0':0,'amp0':1,'gate0':False}}

    def check_remote_values(self):
        return {'channel 0':self.smart_cache['STATIC_DATA']}

    def check_status(self):
        stb = 128

        return self.convert_register(stb)

    def program_manual(self,front_panel_values):
        self.smart_cache['STATIC_DATA'] = front_panel_values['channel 0']
        return self.check_remote_values()

    def transition_to_buffered(self,device_name,h5file,initial_values,fresh):
        VISAWorker.transition_to_buffered(self,device_name,h5file,initial_values,fresh)

    def clear(self,value):
        pass

    def shutdown(self):
        pass
