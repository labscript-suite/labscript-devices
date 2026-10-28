# A labscript device class for data acquisition boards made by Alazar Technologies Inc (ATS)
# Hacked up from NIboard.py by LDT 2017-01-26
#
# Copyright (c) Monash University 2017
from labscript_devices.common.deprecation import deprecated_names

__getattr__ = deprecated_names(
    __name__,
    {
        'labscript_devices': [
            'AlazarTechBoard',
        ],
        'blacs_tabs': [
            'GuilessTab',
        ],
        'blacs_workers': [
            'tqdm_kwargs',
            'atsRanges',
            'atsSampleRates',
            'atsExternalClockAdvice',
            'find_nearest_internal_clock',
            'find_clock_and_r',
            'ats9462_clock',
            'GuilessWorker',
        ],
    },
)
