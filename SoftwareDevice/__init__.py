from labscript_utils import check_version

import sys
if sys.version_info < (3, 5):
    raise RuntimeError("SoftwareDevice requires Python 3.5+")