#####################################################################
#                                                                   #
# /naqslab_devices/PulseBlasterESRPro300/register_classes.py        #
#                                                                   #
#                                                                   #
#####################################################################
import labscript_devices

labscript_devices.register_classes(
    'PulseBlasterESRPro300',
    BLACS_tab='naqslab_devices.PulseBlasterESRPro300.blacs_tab.PulseBlasterESRPro300Tab',
    runviewer_parser='naqslab_devices.PulseBlasterESRPro300.runviewer_parser.PulseBlasterESRProParser',
)
