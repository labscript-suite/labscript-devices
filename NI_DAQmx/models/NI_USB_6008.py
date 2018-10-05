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


from __future__ import division, unicode_literals, print_function, absolute_import
from labscript_utils import PY2

if PY2:
    str = unicode

from labscript_devices.NI_DAQmx.base_class import NI_DAQmx

CAPABILITIES = {
    'AI_range': [-20.0, 20.0],
    'AO_range': [0.0, 5.0],
    'max_AI_multi_chan_rate': 10000.0,
    'max_AI_single_chan_rate': 10000.0,
    'max_AO_sample_rate': None,
    'max_DO_sample_rate': None,
    'num_AI': 8,
    'num_AO': 2,
    'num_CI': 1,
    'ports': {
        'port0': {'num_lines': 8, 'supports_buffered': False},
        'port1': {'num_lines': 4, 'supports_buffered': False},
    },
    'supports_buffered_AO': False,
    'supports_buffered_DO': False,
}


class NI_USB_6008(NI_DAQmx):
    description = 'NI-USB-6008'

    def __init__(self, *args, **kwargs):
        # Any provided kwargs take precedent over capabilities
        combined_kwargs = CAPABILITIES.copy()
        combined_kwargs.update(kwargs)
        NI_DAQmx.__init__(self, *args, **combined_kwargs)
