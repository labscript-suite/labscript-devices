#####################################################################
#                                                                   #
# /naqslab_devices/__init__.py                                      #
#                                                                   #
# Copyright 2018, David Meyer                                       #
#                                                                   #
# This file is part of the naqslab devices extension to the         #
# labscript_suite. It is licensed under the Simplified BSD License. #
#                                                                   #
#                                                                   #
#####################################################################

# basic init for naqslab_devices
# defines a version and author  


import sys
import os

sys.path
sys.path.append(os.getcwd())

import sys
import os




import labscript_devices

__version__ = '0.4.0'
__author__ = ['dihm']

#############################################
# define helper sub-classes of labscript defined channels
# Working constellation from hier is labscript * 3

from labscript import Device, AnalogIn, StaticDDS, LabscriptError
#from labscript.labscript import *


class ScopeChannel(AnalogIn):
    """Subclass of labscript.AnalogIn that marks an acquiring scope channel.
    """
    description = 'Scope Acquisition Channel Class'

    def __init__(self, name, parent_device, connection):
        """This instantiates a scope channel to acquire during a buffered shot.

        Args:
            name (str): Name to assign channel
            parent_device (obj): Handle to parent device
            connection (str): Which physical scope channel is acquiring.
                              Generally of the form \'Channel n\' where n is
                              the channel label.
        """
        Device.__init__(self,name,parent_device,connection)
        self.acquisitions = []

    def acquire(self):
        """Inform BLACS to save data from this channel.

        Note that the parent_device controls when the acquisition trigger is sent.
        """
        if self.acquisitions:
            raise LabscriptError('Scope Channel {0:s}:{1:s} can only have one acquisition!'.format(self.parent_device.name,self.name))
        else:
            self.acquisitions.append({'label': self.name})


class CounterScopeChannel(ScopeChannel):
    """Subclass of :obj:`ScopeChannel` that allows for pulse counting."""
    description = 'Scope Acquisition Channel Class with Pulse Counting'

    def __init__(self, name, parent_device, connection):
        """This instantiates a counter scope channel to acquire during a buffered shot.

        Args:
            name (str): Name to assign channel
            parent_device (obj): Handle to parent device
            connection (str): Which physical scope channel is acquiring.
                              Generally of the form \'Channel n\' where n is
                              the channel label.
        """
        ScopeChannel.__init__(self,name,parent_device,connection)
        self.counts = []

    def count(self,typ,pol):
        """Register a pulse counter operation for this channel.

        Args:
            typ (str): count 'pulse' or 'edge'
            pol (str): reference to 'pos' or 'neg' edges
        """
        # guess we can allow multiple types of counters per channel
        if (typ in ['pulse', 'edge']) and (pol in ['pos', 'neg']):
            self.counts.append({'type':typ,'polarity':pol})
        else:
            raise LabscriptError('Invalid counting parameters for {0:s}:{1:s}'.format(self.parent_name,self.name)) 


class StaticFreqAmp(StaticDDS):
    """A Static Frequency that supports frequency and amplitude control.

    If phase control is needed, use labscript.StaticDDS"""
    description = 'Frequency Source class for Signal Generators'

    def __init__(self, *args, **kwargs):
        """This instatiates a static frequency output channel.

        Frequency and amplitude limits set here will supercede those dictated
        by the device class, but only when compiling a shot with runmanager.
        Static update limits are enforced by the BLACS Tab for the parent device.

        Args:
            *args: Passed to parent init.
            **kwargs: Passed to parent init.

        Raises:
            LabscriptError: If **kwargs contains phase settings, which are not supported.
        """

        if not {'phase_limits','phase_conv_class','phase_conv_params'}.isdisjoint(kwargs.keys()):
            raise LabscriptError(f'{self.device.name} does not support any phase configurations.')

        super().__init__(*args,**kwargs)
        # set default values within limits specified
        # if not specified, use limits from parent device
        parent_device = args[1]
        freq_limits = kwargs.get('freq_limits')
        amp_limits = kwargs.get('amp_limits')
        if freq_limits is not None:
            self.frequency.default_value = freq_limits[0]
        else:
            self.frequency.default_value = parent_device.freq_limits[0]/parent_device.scale_factor
        if amp_limits is not None:
            self.amplitude.default_value = amp_limits[0]
        else:
            self.amplitude.default_value = parent_device.amp_limits[0]/parent_device.amp_scale_factor

    def setphase(self,value,units=None):
        """Overridden from StaticDDS so as not to provide phase control, which
        is generally not supported by :obj:`SignalGenerator` devices.
        """
        raise LabscriptError('StaticFreqAmp does not support phase control')
    
