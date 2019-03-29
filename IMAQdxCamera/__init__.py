from labscript_utils import check_version

from labscript_utils import PY2
if PY2:
    raise RuntimeError("IMAQdxCamera driver not compatible with Python 2")


check_version('labscript_utils', '2.12.1', '3')
check_version('labscript', '2.5.1', '3')