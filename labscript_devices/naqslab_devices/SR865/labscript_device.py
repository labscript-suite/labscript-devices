#####################################################################
#                                                                   #
# /naqslab_devices/SR865/labscript_device.py                        #
#                                                                   #
# Copyright 2018, David Meyer                                       #
#                                                                   #
# This file is part of the naqslab devices extension to the         #
# labscript_suite. It is licensed under the Simplified BSD License. #
#                                                                   #
#                                                                   #
#####################################################################
import numpy as np

from naqslab_devices.VISA.labscript_device import VISA
from labscript import Device, AnalogOut, config, LabscriptError, set_passed_properties

__version__ = '0.1.1'
__author__ = ['dihm']

sens = np.array([1,500e-3,200e-3,100e-3,50e-3,20e-3,10e-3,5e-3,2e-3,1e-3,
                    500e-6,200e-6,100e-6,50e-6,20e-6,10e-6,5e-6,2e-6,1e-6,
                    500e-9,200e-9,100e-9,50e-9,20e-9,10e-9,5e-9,2e-9,1e-9])
                    
tau = np.array([1e-6,3e-6,10e-6,30e-6,100e-6,300e-6,
                1e-3,3e-3,10e-3,30e-3,100e-3,300e-3,
                1,3,10,30,100,300,1e3,3e3,10e3,30e3])
                     
class SR865(VISA):
    description = 'SR865 Lock-In Amplifier'
    allowed_children = None
    
    # initialize these parameters to None
    tau = None
    sens = None
    phase = None

    @set_passed_properties()
    def __init__(self, name, VISA_name):
        '''VISA_name can be full VISA connection string or NI-MAX alias'''
        # does not have a parent device
        VISA.__init__(self,name,None,VISA_name)
        
    def set_tau(self, tau_constant):
        '''Set the time constant in seconds.
        Uses numpy digitize to translate to int values.
        Using digitize corrects for round-off errors and coerces input to 
        nearest allowed setting.'''
        self.tau = tau_constant
        # check that setting is valid
        if tau_constant in tau:
            self.tau_i = np.digitize(tau_constant,tau,right=True)
        else:
            raise LabscriptError('{:s}: tau cannot be set to {:f}'.format(self.VISA_name,self.tau))
        
    def set_sens(self, sensitivity):
        '''Set the sensitivity in Volts
        Uses numpy digitize to translate to int values.
        Using digitize corrects for round-off errors and coerces input to
        nearest allowed setting.'''
        self.sens = sensitivity
        # check that setting is valid
        if sensitivity in sens:
            self.sens_i = np.digitize(sensitivity,sens)
        else:
            raise LabscriptError('{:s}: sensitivity cannot be set to {:f}'.format(self.VISA_name,self.sens))
            
    def set_phase(self, phase):
        '''Set the phase reference in degrees
        Device auto-converts to -180,180 range'''
        self.phase = phase
        
    
    def generate_code(self, hdf5_file):
        '''Generates the transition to buffered code in the h5 file.
        If parameter is not specified in shot, NaN and -1 values are set
        to tell worker not to change the value when programming.'''
        # type the static_table
        static_dtypes = np.dtype({'names':['tau','tau_i','sens','sens_i','phase'],
                            'formats':[np.float16,np.int8,np.float16,np.int8,np.float32]})
        static_table = np.zeros(1,dtype=static_dtypes)
        
        # if tau is set, add tau value to table, else add NaN
        if self.tau:
            static_table['tau'] = self.tau
            static_table['tau_i'] = self.tau_i
        else:
            static_table['tau'] = np.NaN
            static_table['tau_i'] = -1
        # if sensitivity is set, add sens to table, else add NaN
        if self.sens:
            static_table['sens'] = self.sens
            static_table['sens_i'] = self.sens_i
        else:
            static_table['sens'] = np.NaN
            static_table['sens_i'] = -1
        # if phase set, add to table, else NaN
        if self.phase:
            static_table['phase'] = self.phase
        else:
            static_table['phase'] = np.NaN

        grp = hdf5_file.create_group('/devices/'+self.name)
        grp.create_dataset('STATIC_DATA',compression=config.compression,data=static_table) 
        # add these values to device properties for easy lookup
        if self.tau: self.set_property('tau', self.tau, location='device_properties')
        if self.sens: self.set_property('sensitivity', self.sens, location='device_properties')
        if self.phase: self.set_property('phase',self.phase,location='device_properties')
