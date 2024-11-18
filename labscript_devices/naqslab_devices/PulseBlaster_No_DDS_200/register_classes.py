#####################################################################
#                                                                   #
# /naqslab_devices/PulseBlaster_No_DDS_200/register_classes.py      #
#                                                                   #
#                                                                   #
#####################################################################
import labscript_devices

labscript_devices.register_classes(
    'PulseBlaster_No_DDS_200',
    BLACS_tab='naqslab_devices.PulseBlaster_No_DDS_200.blacs_tab.PulseBlaster_No_DDS_200_Tab',
    runviewer_parser='naqslab_devices.PulseBlaster_No_DDS_200.runviewer_parser.PulseBlaster_No_DDS_200_Parser',
)
