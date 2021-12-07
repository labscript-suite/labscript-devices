#####################################################################
#                                                                   #
# /NI_DAQmx/models/_subclass_template.py                            #
#                                                                   #
# Copyright 2018, Christopher Billington                            #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################

#####################################################################
#     WARNING                                                       #
#                                                                   #
# This file is auto-generated, any modifications may be             #
# overwritten. See README.txt in this folder for details            #
#                                                                   #
#####################################################################


from labscript_devices.NI_DAQmx.labscript_devices import NI_DAQmx

#:
CAPABILITIES = {
    'AI_range': [-10.0, 10.0],
    'AI_range_Diff': [-10.0, 10.0],
    'AI_start_delay': 2.5e-07,
    'AI_term': 'RSE',
    'AI_term_cfg': {
        'ai0': ['RSE', 'NRSE', 'Diff'],
        'ai1': ['RSE', 'NRSE', 'Diff'],
        'ai10': ['RSE', 'NRSE'],
        'ai11': ['RSE', 'NRSE'],
        'ai12': ['RSE', 'NRSE'],
        'ai13': ['RSE', 'NRSE'],
        'ai14': ['RSE', 'NRSE'],
        'ai15': ['RSE', 'NRSE'],
        'ai2': ['RSE', 'NRSE', 'Diff'],
        'ai3': ['RSE', 'NRSE', 'Diff'],
        'ai4': ['RSE', 'NRSE', 'Diff'],
        'ai5': ['RSE', 'NRSE', 'Diff'],
        'ai6': ['RSE', 'NRSE', 'Diff'],
        'ai7': ['RSE', 'NRSE', 'Diff'],
        'ai8': ['RSE', 'NRSE'],
        'ai9': ['RSE', 'NRSE'],
    },
    'AO_range': [-10.0, 10.0],
    'max_AI_multi_chan_rate': 1000000.0,
    'max_AI_single_chan_rate': 1250000.0,
    'max_AO_sample_rate': 2857142.8571428573,
    'max_DO_sample_rate': 10000000.0,
    'min_semiperiod_measurement': 1e-07,
    'num_AI': 16,
    'num_AO': 2,
    'num_CI': 2,
    'ports': {
        'port0': {'num_lines': 8, 'supports_buffered': True},
        'port1': {'num_lines': 8, 'supports_buffered': False},
        'port2': {'num_lines': 8, 'supports_buffered': False},
    },
    'supports_buffered_AO': True,
    'supports_buffered_DO': True,
    'supports_semiperiod_measurement': True,
    'supports_simultaneous_AI_sampling': False,
}


class NI_PCI_6251(NI_DAQmx):
    description = 'NI-PCI-6251'

    def __init__(self, *args, **kwargs):
        """Class for NI-PCI-6251"""
        # Any provided kwargs take precedent over capabilities
        combined_kwargs = CAPABILITIES.copy()
        combined_kwargs.update(kwargs)
        NI_DAQmx.__init__(self, *args, **combined_kwargs)
