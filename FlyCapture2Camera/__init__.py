
import sys
if sys.version_info < (3,6):
    raise RuntimeError("FlyCapture2Camera strongly prefers Python 3.6+")

try:
    # must install PyCapture2 compatible with python version
    import PyCapture2
    ver = PyCapture2.getLibraryVersion()
    min_ver = (2,12,3,31) # first release with python 3.6 support
    if ver < min_ver:
        raise RuntimeError(f"PyCapture2 version {ver} must be >= {min_ver}")

except ImportError as e:
    raise Exception('Cannot import PyCapture2. Is it installed in correct environment?') from e
