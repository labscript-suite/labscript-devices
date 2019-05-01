from labscript_utils import check_version

import sys
if sys.version_info < (3, 6):
    raise RuntimeError("IMAQdxCamera driver requires Python 3.6+")


check_version('labscript_utils', '2.12.1', '3')
check_version('labscript', '2.5.2', '3')