from labscript_utils import check_version

import sys
if sys.version_info < (2, 7):
    raise RuntimeError("Pylon API requires Python 2.7+")
elif sys.version_info > (2,7) and sys.version_info < (3,6):
    raise RuntimeError("PylonCamera strongly prefers Python 3 with minor version 6+")

check_version('labscript_utils', '2.12.1', '3')
check_version('labscript', '2.5.2', '3')
