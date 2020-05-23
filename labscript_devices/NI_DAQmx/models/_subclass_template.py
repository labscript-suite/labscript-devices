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

${AUTOGENERATION_WARNING}

from labscript_devices.NI_DAQmx.labscript_devices import NI_DAQmx

CAPABILITIES = ${CAPABILITIES}


class ${CLASS_NAME}(NI_DAQmx):
    description = '${MODEL_NAME}'

    def __init__(self, *args, **kwargs):
        # Any provided kwargs take precedent over capabilities
        combined_kwargs = CAPABILITIES.copy()
        combined_kwargs.update(kwargs)
        NI_DAQmx.__init__(self, *args, **combined_kwargs)