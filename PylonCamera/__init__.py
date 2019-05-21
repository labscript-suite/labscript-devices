from labscript_utils import check_version

import sys
if sys.version_info < (2, 7):
    raise RuntimeError("PylonCamera driver requires Python 2.7+")

check_version('labscript_utils', '2.12.1', '3')
check_version('labscript', '2.5.2', '3')
