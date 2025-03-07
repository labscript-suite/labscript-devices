"""
Keysight DSOX1202G
Two types of properties:
    * Osci specific properties
    * Shot-specific configurations

"""

# -----------------------------------  Keysight DSOX1202G
osci_shot_configuration = {
    # Channel unrelated
    "trigger_source"        :     "CHANnel1",       #  CHANnel1, CHANnel2 , EXTernal , LINE , WGEN  
    "trigger_level"         :     "1",            #
    "trigger_level_unit"    :     "V",              # V or mV
    "trigger_type"          :     "EDGE",           # 
    "trigger_edge_slope"    :     "POSitive",       # Only for trigger type is Edge 

    # "triggered"             :      False,           # Flag to keep track of triggers    (Onyl when Trigger is External)    

    "acquire_type"          :     "NORMal",         # NORMal , AVERage , HRESolution , PEAK (TO DO HRESOLUTION and PEAK)
    "acquire_count"         :      "8",            # AVERage=2-65536 ,HRESolution=1 ,NORMal=8 , PEAK=None

    "waveform_format"       :      "WORD",          # WORD , BYTE          # Sometimes: despite the format is Word , the osci still sends Byte data, unclear ?   

    "time_reference"        :     "LEFT",           # LEFT , CENT , RIGH 
    "time_division"         :     "50",             #
    "time_division_unit"    :     "us",             # s, ms , us , ns
    "time_delay"            :     "0",              #
    "time_delay_unit"       :     "us",             # s, ms , us , ns

    "timeout"               :     "5",              # In seconds    


    # Channel related
    # ------------------------ Channel 1 
    "channel_display_1"       :     "1",              # 1 ON , 0 = OFF

    "voltage_division_1"      :     "1",              # 
    "voltage_division_unit_1" :     "V",              # V or mV
    "voltage_offset_1"        :     "0",              #
    "voltage_offset_unit_1"   :     "V",              # V or mV
    "probe_attenuation_1"     :     "1",              # 

    # ------------------------ Channel 2         
    "channel_display_2"       :     "0",              # 1 ON , 0 = OFF

    "voltage_division_2"      :     "1",              # 
    "voltage_division_unit_2" :     "V",              # V or mV
    "voltage_offset_2"        :     "0",              #
    "voltage_offset_unit_2"   :     "V",              # V or mV
    "probe_attenuation_2"     :     "1"               # 

}

{
  'added_properties': {}, 
  'start_order': 0, 
  'stop_order': 0, 
}


# -----------------------------------  Keysight DSOX1202G
osci_capabilities = {
        "description"     :     "Example Osci",
        "serial_number"   :     "CN61364200",
        "band_width"      :       70e6,              # 70 MHz
        "sampling_rate"   :       2*1e9,            # 2GSa/s
        "max_memory"      :       1e6,               # 1Mpts
        "max_update_rate" :       5e4                # 50,000 waveforms/second update rate.   
}



# ----------------------------------- Tests 
if __name__ == "__main__":
    class Osci:
        def __init__(self, 
                     osci_capabilities, 
                     osci_shot_configuration):
            
            for key, value in osci_capabilities.items():
                setattr(self, key, value)

            for key, value in osci_shot_configuration.items():
                setattr(self, key, value)

        
    spec = Osci(
            osci_capabilities = osci_capabilities,
            osci_shot_configuration = osci_shot_configuration)
    
    print(spec.sampling_rate)
    print(spec.timeout)



