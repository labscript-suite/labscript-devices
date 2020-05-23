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

CAPABILITIES = {
    'AI_range': None,
    'AI_start_delay': None,
    'AO_range': [-10.0, 10.0],
    'max_AI_multi_chan_rate': None,
    'max_AI_single_chan_rate': None,
    'max_AO_sample_rate': 1000000.0,
    'max_DO_sample_rate': 10000000.0,
    'min_semiperiod_measurement': 2e-05,
    'num_AI': 0,
    'num_AO': 8,
    'num_CI': 2,
    'ports': {'port0': {'num_lines': 8, 'supports_buffered': True}},
    'supports_buffered_AO': True,
    'supports_buffered_DO': True,
    'supports_semiperiod_measurement': True,
}


class NI_PCI_6733(NI_DAQmx):
    description = 'NI-PCI-6733'

    def __init__(self, *args, **kwargs):
        # Any provided kwargs take precedent over capabilities
        combined_kwargs = CAPABILITIES.copy()
        combined_kwargs.update(kwargs)
        NI_DAQmx.__init__(self, *args, **combined_kwargs)
