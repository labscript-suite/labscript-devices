import sys
from labscript_devices import labscript_device, BLACS_tab, BLACS_worker, runviewer_parser 

@labscript_device
class test_device(object):
    pass

@BLACS_tab
class Tab(object):
    pass
    
@BLACS_worker
class Worker(object):
    pass
    
@runviewer_parser
class Parser(object):
    pass
