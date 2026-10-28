# A labscript device class for data acquisition boards made by Alazar Technologies Inc (ATS)
# Hacked up from NIboard.py by LDT 2017-01-26
#
# Copyright (c) Monash University 2017
import labscript_devices

labscript_devices.register_classes(
    'AlazarTechBoard',
    BLACS_tab='labscript_devices.AlazarTechBoard.blacs_tabs.GuilessTab',
)
