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
    'AI_start_delay': None,
    'AI_start_delay_ticks': 64,
    'AI_term': 'PseudoDiff',
    'AI_term_cfg': {
        'ai0': ['PseudoDiff'],
        'ai1': ['PseudoDiff'],
        'ai10': ['PseudoDiff'],
        'ai11': ['PseudoDiff'],
        'ai12': ['PseudoDiff'],
        'ai13': ['PseudoDiff'],
        'ai14': ['PseudoDiff'],
        'ai15': ['PseudoDiff'],
        'ai2': ['PseudoDiff'],
        'ai3': ['PseudoDiff'],
        'ai4': ['PseudoDiff'],
        'ai5': ['PseudoDiff'],
        'ai6': ['PseudoDiff'],
        'ai7': ['PseudoDiff'],
        'ai8': ['PseudoDiff'],
        'ai9': ['PseudoDiff'],
    },
    'AO_range': None,
    'max_AI_multi_chan_rate': 204800.0,
    'max_AI_single_chan_rate': 204800.0,
    'max_AO_sample_rate': None,
    'max_DO_sample_rate': None,
    'min_semiperiod_measurement': None,
    'num_AI': 16,
    'num_AO': 0,
    'num_CI': 0,
    'ports': {},
    'supports_buffered_AO': False,
    'supports_buffered_DO': False,
    'supports_semiperiod_measurement': False,
    'supports_simultaneous_AI_sampling': True,
}


class NI_PXIe_4499(NI_DAQmx):
    description = 'NI-PXIe-4499'

    def __init__(self, *args, **kwargs):
        """Class for NI-PXIe-4499"""
        # Any provided kwargs take precedent over capabilities
        combined_kwargs = CAPABILITIES.copy()
        combined_kwargs.update(kwargs)
        NI_DAQmx.__init__(self, *args, **combined_kwargs)
