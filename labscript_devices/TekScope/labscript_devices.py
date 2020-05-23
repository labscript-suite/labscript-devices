from labscript import Device, LabscriptError, set_passed_properties

class TekScope(Device):
    """A labscript_device for Tektronix oscilloscopes using a visa interface.
          connection_table_properties (set once)
          termination: character signalling end of response
          preamble_string: base command for waveform preamble ('WFMO' or 'WFMP')

          device_properties (set per shot)
          timeout: in seconds for response to queries over visa interface
          int16: download waveform pts as 16 bit integers (returns 1/2 as many pts) 
    """
    description = 'Tekstronix oscilloscope'

    @set_passed_properties(
        property_names = {
            'connection_table_properties': ['termination', 'preamble_string'],
            'device_properties': ['timeout', 'int16']}
        )
    def __init__(self, name, addr, 
                 termination='\n', preamble_string='WFMP',
                 timeout=5, int16=False,
                 **kwargs):
        Device.__init__(self, name, None, addr, **kwargs)
        self.name = name
        self.BLACS_connection = addr
        self.termination = termination
        self.preamble_string = preamble_string
        assert preamble_string in ['WFMO', 'WFMP'], "preamble_string must be one of 'WFMO' or 'WFMP'"

    def generate_code(self, hdf5_file):
        # group = self.init_device_name(hdf5_file)
        Device.generate_code(self, hdf5_file)
