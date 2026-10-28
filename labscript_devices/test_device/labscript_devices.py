from labscript import Device, LabscriptError, set_passed_properties


class test_device(Device):
    description = 'test device'
    
    @set_passed_properties(
        property_names = {
                 "connection_table_properties": ["name"],
                 "device_properties": ["DoSomething"]}
        )
    def __init__(self, name, DoSomething = False, **kwargs):
        if DoSomething is not False:
            raise LabscriptError('test_device does nothing, but kwarg DoSomething was not passed False')


        Device.__init__(self, name, None, None, **kwargs)
