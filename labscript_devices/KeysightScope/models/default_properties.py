"""
*************************** DON't DELETE THIS FILE
Idea:

    - Initializing a device for experiments starts by adding it to the connection table file.
    For example: KeysightScope(name="Keysight_Osci", ....)

    - To set the device in a specific state in the initialization, we pass a dictionary that contains the desired configuration for the device.

    - This dictionary will be passed to the labscript_device class.

    ********************* The purpose of this file *********************
    - For proper setup, we must first pass a default dictionary to the decorator responsible for configuring the device properties. 
    This is necessary because the labscript_device class needs to know the properties to be initialized before the device itself is initialized.
    *********************************************************************

    - These properties will be overridden when initializing the device.

    - This approach is made possible by the way labscript is designed (see labscript.set_passed_properties for more details).
"""

# -----------------------------------  Keysight DSOX1202G
default_osci_shot_configuration = {
    "configuration_number"  :     None,                 # General Setup Number
    # Channel unrelated
    "trigger_source"        :     None,                 #  CHANnel1, CHANnel2 , EXTernal , LINE , WGEN  
    "trigger_level"         :     None,                 #
    "trigger_level_unit"    :     None,                 # V or mV
    "trigger_type"          :     None,                 # 
    "trigger_edge_slope"    :     None,                 # Only for trigger type is Edge 

    "triggered"             :     None,                 # Flag to keep track of triggers    (TO DO)    

    "acquire_type"          :     None,                 # NORMal , AVERage , HRESolution , PEAK (TO DO HRESOLUTION and PEAK)
    "acquire_count"         :     None,                 # AVERage=2-65536 ,HRESolution=1 ,NORMal=8 , PEAK=None

    "waveform_format"       :     None,                 # WORD , BYTE          # WORD doesnt work 

    "time_reference"        :     None,                 # LEFT , CENT , RIGH 
    "time_division"         :     None,                 #
    "time_division_unit"    :     None,                 # s, ms , us , ns
    "time_delay"            :     None,                 #
    "time_delay_unit"       :     None,                 # s, ms , us , ns

    "timeout"               :     None,                 # In seconds    

    # Channel related
    # ------------------------ Channel 1 
    "channel_display_1"       :     None,              # 1 ON , 0 = OFF

    "voltage_division_1"      :     None,              # 
    "voltage_division_unit_1" :     None,              # V or mV
    "voltage_offset_1"        :     None,              #
    "voltage_offset_unit_1"   :     None,              # V or mV
    "probe_attenuation_1"     :     None,              # 

    # ------------------------ Channel 2         
    "channel_display_2"       :     None,              # 1 ON , 0 = OFF

    "voltage_division_2"      :     None,              # 
    "voltage_division_unit_2" :     None,              # V or mV
    "voltage_offset_2"        :     None,              #
    "voltage_offset_unit_2"   :     None,              # V or mV
    "probe_attenuation_2"     :     None               # 
}

# -----------------------------------  Keysight DSOX1202G
default_osci_capabilities = {
        "serial_number"   :       None,      # Important to write
        "band_width"      :       None,      # 70 MHz
        "sampling_rate"   :       None,      # 2GSa/s
        "max_memory"      :       None,      # 1Mpts
        "max_update_rate" :       None       # 50,000 waveforms/second update rate.   
}




