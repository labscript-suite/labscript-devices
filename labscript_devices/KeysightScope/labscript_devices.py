from labscript import Device, LabscriptError, set_passed_properties ,LabscriptError, AnalogIn



class KeysightScope(Device):
    """A labscript_device for Keysight oscilloscopes (DSOX1202G) using a visa interface.
          - connection_table_properties (set once)
          - device_properties (set per shot)
                * timeout : in seconds for response to queries over visa interface
                * int16   : download waveform pts as 16 bit integers 
    """
    description = 'Keysight' 
    #allowed_children = [ScopeChannel]

    

    @set_passed_properties(
        property_names = {
            'device_properties': ['timeout', 'int16']
            }
        )
    def __init__(self, name, addr, 
                 timeout=5, int16=False,
                 **kwargs):
        Device.__init__(self, name, None, addr, **kwargs)
        self.name = name
        self.BLACS_connection = addr
        self.acquisitions = []                      # already defined in the class ÁnalogIn 


    # ----------------------------------------------- TO DOs
    def _check_AI_not_too_fast(self, AI_table):     # TO DO
        pass

    def _make_analog_input_table(self, inputs):     # TO DO 
        pass 

    def generate_code(self, hdf5_file, *args):      # To improve
    # group = self.init_device_name(hdf5_file)
        Device.generate_code(self, hdf5_file)
    # save self.acquisitions in hdf5



