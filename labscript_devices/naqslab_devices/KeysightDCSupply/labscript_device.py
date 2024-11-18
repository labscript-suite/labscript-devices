#####################################################################
#                                                                   #
# /naqslab_devices/KeysightDCSupply/labscript_device.py             #
#                                                                   #
# Copyright 2020, David Meyer                                       #
#                                                                   #
# This file is part of the naqslab devices extension to the         #
# labscript_suite. It is licensed under the Simplified BSD License. #
#                                                                   #
#                                                                   #
#####################################################################
import numpy as np

from naqslab_devices.VISA.labscript_device import VISA
from labscript import StaticAnalogOut, LabscriptError, set_passed_properties, config

__version__ = '0.1.0'
__author__ = ['dihm']

# note, when adding a new model, put the labscript_device inheritor class
# into Models.py and the BLACS classes into a file named for the device
# in the BLACS subfolder. Update register_classes.py and __init__.py
# accordingly.
                    
class KeysightDCSupply(VISA):
    description = 'DC Power Supply'
    allowed_children = [StaticAnalogOut]
    allowed_outputs = [0]  


    @set_passed_properties(property_names = {'connection_table_properties':
            ['volt_limits','current_limits','range','limited','allowed_outputs']})
    def __init__(self, name, VISA_name, 
                range='LOW', volt_limits=(0,1), current_limits=(0,1), limited='volt'):
        '''Keysight DC Power Supply

        The labscript_device for Keysight DC Power supplies. Currently only tested
        for E364xA single output series devices.

        Args:
            name (str): labscript name to assign to device. Must be an allowed python variable name.
            VISA_name (str): VISA connection string to device. Can be alias configured in NI-MAX.
            range (str): configures which voltage range to use. Default is 'LOW'.
            volt_limits (iterable): voltage limits, in volts
            current_limits (iterable): current limits, in amps
            limited (str): Sets whether output is configured to be voltage or current limited. Default is 'volt'
        '''
        
        # validate and save configuration parameters
        if range in ('LOW','HIGH'):
            self.range = range
        else:
            msg = f'''Invalid value {range} for range.
                Must be either \'LOW\' or \'HIGH\'.'''
            raise LabscriptError(msg)

        try:
            iter(volt_limits)
        except TypeError:
            msg = f'''volt_limits must be of iterable type, not {str(type(volt_limits))}'''
            raise LabscriptError(msg)
        else:
            if len(volt_limits) != 2:
                msg = f'''volt_limits must have two elements: (lower,upper), not {volt_limits}'''
                raise LabscriptError(msg)

        try:
            iter(current_limits)
        except TypeError:
            msg = f'''current_limits must be of iterable type, not {str(type(current_limits))}'''
            raise LabscriptError(msg)
        else:
            if len(current_limits) != 2:
                msg = f'''current_limits must have two elements: (lower,upper), not {current_limits}'''
                raise LabscriptError(msg)

        self.volt_limits = volt_limits
        self.current_limits = current_limits

        if limited in ('volt','current'):
            self.limited = limited
        else:
            msg = f'''Invalid value {limited} for limited. 
                Must be either \'volt\' or \'current\'.'''
            raise LabscriptError(dedent(msg))
        # DC Power Supplies do not have a parent device
        VISA.__init__(self,name,None,VISA_name)
        
    def quantise_volt(self,data,output):
        '''Quantize the currents in units of V and check it's within bounds'''                       

        # Ensure that amplitudes are within bounds:        
        if data < self.volt_limits[0]  or data > self.volt_limits[1]:
            msg = '''{:s} {:s} can only have volts between 
                {:.5f} V and {:.5f} V, {} given'''.format(output.description, 
                                                output.name,*self.amp_limits,
                                                data)
            raise LabscriptError(dedent(msg))
        return data

    def quantise_current(self,data,output):
        '''Quantize the currents in units of A and check it's within bounds'''                       

        # Ensure that amplitudes are within bounds:        
        if data < self.current_limits[0]  or data > self.current_limits[1]:
            msg = '''{:s} {:s} can only have currents between 
                {:.5f} A and {:.5f} A, {} given'''.format(output.description, 
                                                output.name,*self.current_limits,
                                                data)
            raise LabscriptError(dedent(msg))
        return data
    
    def generate_code(self, hdf5_file):

        chan_num = len(self.child_devices)
        if not chan_num:
            print(f'No outputs attached to {self.name:s}')
            return

        outputs = {}
        for output in self.child_devices:
            try:
                prefix, channel = output.connection.split(' ')
                channel = int(channel)
                outputs[channel] = output
            except :
                msg = '''{:s} {:s} has invalid connection string: \'{!s}\'.
                Format must be \'channel n\' with n an integer.'''
                raise LabscriptError(dedent(msg.format(output.description,
                                            output.name,output.connection)))

        # create static table and populate
        static_dtypes = np.dtype({'names':['channel %d'%i for i in outputs.keys()],
                                'formats':[np.float16 for i in outputs.keys()]})
        static_table = np.zeros(1, dtype=static_dtypes)
        for channel, output in outputs.items(): 
            if channel not in self.allowed_outputs:
                msg = '''channel {} not in {}.'''
                raise LabscriptError(dedent(msg.format(channel,self.allowed_outputs)))

            _ = output.get_change_times()
            _ = output.make_timeseries([])
            _ = output.expand_timeseries()

            if self.limited == 'volt':
                raw_output = self.quantise_volt(output.static_value,output)
            else:
                raw_output = self.quantise_current(output.static_value,output)

            static_table['channel %d'%channel] = raw_output
        
        grp = hdf5_file.create_group('/devices/'+self.name)
        grp.create_dataset('STATIC_DATA',compression=config.compression,data=static_table) 

