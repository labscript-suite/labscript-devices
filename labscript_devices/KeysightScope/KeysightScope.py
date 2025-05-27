import pyvisa
import numpy as np
from labscript.labscript import LabscriptError


class KeysightScopeDevice: 
    def __init__(self,
                 address,
                 verbose = False
                 ):
        
        self.verbose = verbose

        self.unit_conversion = {
            's' : 1  ,  
            'ns': 1e-9,  # nanoseconds to seconds
            'us': 1e-6,  # microseconds to seconds
            'ms': 1e-3   # milliseconds to seconds
            }

        # --------------------------------- Connecting to device 
        self.dev = pyvisa.ResourceManager().open_resource(address)
        print(f'Initialized: {self.dev.query("*IDN?")}')
        
        # --------------------------------- Initialize device
        self.reset_device() 

    #######################################################################################
    #                             Saving and Recalling                                    #
    ####################################################################################### 
    def get_settings_dict(self,value):  
        """
          Returns a configuration dictionary for the oscilloscope memory slot specified by 'value'.
          Args:
            value (int or str): The memory slot number of the oscilloscope from which to retrieve the configuration.

        """
        osci_shot_configuration = {
        "configuration_number"  : str(value) ,

        # Channel unrelated
        "trigger_source"        : str(self.get_trigger_source()).strip(),       
        "trigger_level"         : str(self.get_trigger_level()).strip(),            
        "trigger_level_unit"    : "V",             
        "trigger_type"          : str(self.get_trigger_type()).strip(),          
        "trigger_edge_slope"    : str(self.get_trigger_edge_slope()).strip(),                  

        "acquire_type"          : str(self.get_acquire_type()).strip(),         
        "acquire_count"         : str(self.get_acquire_count()).strip(),            
        "waveform_format"       : str(self.get_waveform_format()).strip(),          

        "time_reference"        : str(self.get_time_reference()).strip(),           
        "time_division"         : str(self.get_time_division()).strip(),
        "time_division_unit"    : "s",             
        "time_delay"            : str(self.get_time_delay()).strip(),          
        "time_delay_unit"       : "s",            
  
        # Channel related
        # ------------------------ Channel 1 
        "channel_display_1"       : str(self.get_channel_display(channel=1)).strip(),            
        "voltage_division_1"      : str(self.get_voltage_division()).strip(),             
        "voltage_division_unit_1" : "V",              
        "voltage_offset_1"        : str(self.get_voltage_offset()).strip(),              
        "voltage_offset_unit_1"   : "V",              
        "probe_attenuation_1"     : str(self.get_probe_attenuation(channel=1)).strip(),              

        # ------------------------ Channel 2         
        "channel_display_2"       : str(self.get_channel_display(channel=2)).strip(),             
        "voltage_division_2"      : str(self.get_voltage_division(channel=2)).strip(),             
        "voltage_division_unit_2" : "V",              
        "voltage_offset_2"        : str(self.get_voltage_offset(channel=2)).strip(),              
        "voltage_offset_unit_2"   : "V",              
        "probe_attenuation_2"     : str(self.get_probe_attenuation(channel=2)).strip()               
        }
        return osci_shot_configuration

    def save_start_setup(self, location = 0):
        """
        Saves the oscilloscope current configuration to a specified location.

        This method sends a command to the oscilloscope to save the current configuration 
        to the specified location. The default location is "0", but any valid location 
        index can be provided.

        Args:
            location (str or int, optional): The index of the configuration location to recall. 
                                    Defaults to "0" if not provided.
        """
        self.dev.write(f":SAVE:SETup:STARt {location}")


    def recall_start_setup(self, location = 0):
        """
        Sets the oscilloscope configuration to a specified location.

        This method sends a command to the oscilloscope to recall and apply the configuration 
        stored at the specified location. The default location is "0", but any valid location 
        index can be provided.

        Args:
            location (str or int, optional): The index of the configuration location to recall. 
                                    Defaults to "0" if not provided.
        """
        return self.dev.query(f":RECall:SETup:STARt {location};*OPC?")

        
        

    def get_saving_register(self):
        """
            Retrieves the configuration settings for all 10 available saving slots of the device.

            Returns:
                dict: A dictionary containing the settings for each of the 10 saving slots.
                    The keys are the slot indices (0 to 9), and the values are dictionaries 
                    with the configuration settings for the corresponding slot. If an error 
                    occurs during the retrieval of a slot's settings, for example because the slot is empty, the value will be an 
                    empty dictionary.
            
            Example:
                saving_register = device.get_saving_register()
                # saving_register will be a dictionary, e.g.:
                # {0: {'setting1': value1, 'setting2': value2}, 
                #  1: {}, 
                #  2: {'setting1': value1}, 
                #  ...}
        """
        saving_register = {}
        for i in range(10):
            self.recall_start_setup(f"{i}")
            if "250" in self.dev.query(":SYSTem:ERRor?"):
                saving_register[i] = {}
            else: saving_register[i] = self.get_settings_dict(i)
        return saving_register
    
    #######################################################################################
    #                               Basic Commands                                        #
    #######################################################################################

    def get_acquire_state(self):    
        """Determine wether the oscilloscope is running.
        Returns: ``True`` if running, ``False`` otherwise
        """
        reg = int(self.dev.query(':OPERegister:CONDition?')) # The third bit of the operation register is 1 if the instrument is running
        return int((reg & 8) == 8)

    def set_acquire_state(self, running=True):
        '''RUN / STOP '''
        self.dev.write(':RUN' if running else 'STOP')
        if self.verbose:
            print("Done running")

    def reset_device(self):
        self.dev.write("*RST")
        if self.verbose:
            print("Done reset")

    def digitize(self):                                
        ''' Specialized RUN command. 
                        acquires a single waveforms according to the settings of the :ACQuire commands subsystem.
                        When the acquisition is complete, the instrument is stopped.
        '''
        self.dev.write(":DIG")

    def autoscale(self):
        self.dev.write(":AUToscale")

    def clear_status(self):
        """
        clears:     the status data structures, 
                    the device-defined error queue,
                    and the Request-for-OPC flag
        """
        self.dev.write("*CLS")
    
    def close(self):
        self.dev.close()

    def lock(self):
        self.dev.write(':SYSTem:LOCK 1')

    def unlock(self):
        self.dev.write(':SYSTem:LOCK 0')

    #######################################################################################
    #                        Setting Axes (Voltage & Time)                                #
    #######################################################################################

    # ----------------------------------------------- Set Voltage
    def set_voltage_range(self, range, channel=1, unit="V"):
        """ unit : V or mV """
        if unit =="V":
            self.dev.write(f":CHANnel{channel}:RANGe {range}")
        elif unit =="mV":
            self.dev.write(f":CHANnel{channel}:RANGe {range}mV")

    def set_voltage_division(self, division, channel=1, unit="V"):
        """ unit : V or mV """
        if unit in ["V","mV"]:
            self.dev.write(f":CHANnel{channel}:SCALe {division}{unit}")
            if self.verbose:
                print("Done voltage division")
   
    def set_voltage_offset(self,offset,channel=1,unit="V"):
        """ unit : V or mV """
        if unit in ["V","mV"]:
            self.dev.write(f":CHANnel{channel}:OFFSet {offset}{unit}")
            if self.verbose:
                print("Done voltage offset")

    # ----------------------------------------------- Get Voltage
    def get_voltage_range(self, channel=1):
        """
        Retrieves the voltage range of the channel in volts (V).

        Returns:
            str: The voltage range in volts (V).
        """
        return self.dev.query(f":CHANnel{channel}:RANGe?")

    def get_voltage_division(self, channel=1):
        """ Get Voltage division of channel in V. """
        return float(self.dev.query(f":CHANnel{channel}:SCALe?"))

    def get_voltage_offset(self,channel=1):
        """ Get Voltage offset of channel in V. """
        return float(self.dev.query(f":CHANnel{channel}:OFFSet?"))

    # ----------------------------------------------- Set Time 
    def set_time_range(self, range, unit):
        """Set the time range of the oscilloscope.
        Args:
            time_range (str or float):: The time range value. (50ns - 500s)
            unit: The unit for the time range, 'ms', 'us', 'ns'.
            
        Raises:
            LabscriptError: If the time range is outside the valid range or if the unit is invalid.
        """

        # Validate unit
        if unit not in self.unit_conversion:
            raise LabscriptError(f"Invalid unit '{unit}'. Supported units are 'ns', 'us', 'ms'.")
        
        # Convert to seconds
        try:
            converted_time_range = float(range) * self.unit_conversion[unit]
            
            # Check if the converted time range is within the allowed bounds
            if not (50e-9 <= converted_time_range <= 500):
                raise LabscriptError(f"Range not supported. Valid range is between 50 ns and 500 s.")
                
        except Exception as e:
            raise LabscriptError(f"Invalid time range or unit: {e}")
        
        # Send the command to the oscilloscope
        self.dev.write(f":TIMebase:RANGe {converted_time_range}")

    def set_time_division(self,division,unit):
        """ Set the time per division of the oscilloscope.
        Args:
            time_division (str or float): The time division value. (min 5ns - max 50s)
            unit: The unit for the time division, 'ms', 'us', 'ns'.
            
        Raises:
            LabscriptError: If the time division is outside the valid division or if the unit is invalid.
        """
        # Validate unit
        if unit not in self.unit_conversion:
            raise LabscriptError(f"Invalid unit '{unit}'. Supported units are 'ns', 'us', 'ms'.")
        
        # Convert to seconds
        try:
            converted_time_division = float(division) * self.unit_conversion[unit]
            
            # Check if the converted time division is within the allowed bounds
            if not (5e-9 <= converted_time_division <= 50):
                raise LabscriptError(f"Time division not supported. Valid division is between 50 ns and 500 s.")
            
        except Exception as e:
            raise LabscriptError(f"Invalid time division or unit: {e}")
        
        self.dev.write(f":TIMebase:SCALe {converted_time_division}")
        if self.verbose:
                print("Done time division")

    def set_time_delay(self,delay,unit="us"):
        """ Set the time delay.
        Args:
            time_delay (str or foat): The time delay value.
            unit: The unit for the time delay, 'ms', 'us', 'ns'.
            
        Raises:
            LabscriptError: If the time delay is outside the valid range or if the unit is invalid.
        """

        # Validate unit
        if unit not in self.unit_conversion:
            raise LabscriptError(f"Invalid unit '{unit}'. Supported units are 'ns', 'us', 'ms'.")

        # Convert to seconds
        try:
            converted_time_delay = float(delay) * self.unit_conversion[unit]
            
            # Check if the converted time range is within the allowed bounds
            if converted_time_delay >= 500:
                raise LabscriptError(f"Time delay not supported. Valid division is between 100ps and 500 s.")
            
        except Exception as e:
            raise LabscriptError(f"Invalid time delay or unit: {e}")

        self.dev.write(f":TIMebase:DELay {converted_time_delay}")
        if self.verbose:
                print("Done time delay")

    def set_time_reference(self,reference = "CENTer"):
        """ accepted args: LEFT , CENTer , RIGHt """
        self.dev.write(f":TIMebase:REFerence {reference}")
        if self.verbose:
                print("Done time reference")

    def set_time_mode(self,mode= "MAIN"):
        """ Set the time mode of the oscilloscope.
        Args:
            mode (str):
            - MAIN : This is the primary mode used in an oscilloscope, 
            delivering a real-time graph of voltage (Y-axis) versus time (X-axis).

            - WINDow :  In the WINDow (zoomed or delayed) time base mode,
            measurements are made in the zoomed time base if possible; otherwise, the
            measurements are made in the main time base.
            If chosen, we still need to set : position, Range, scale
            (Not adequate for retrieving data.)

            - XY: The X-Y mode plots one voltage against another. 
            Therefore :TIMebase:RANGe, :TIMebase:POSition, and :TIMebase:REFerence commands are not available in this mode

            - Roll : Idea for low frequeny signals.  In this mode, the waveform scrolls from right to left across the display
        
        """
        self.dev.write(f":TIMebase:MODE {mode}")

    # ----------------------------------------------- Get Time 
    def get_time_range(self):
        """ Retrieves the global time range in s"""
        return self.dev.query(":TIMebase:RANGe?")

    def get_time_division(self):
        """ Retrieves the time division in s. """     
        return self.dev.query(":TIMebase:SCALe?")

    def get_time_delay(self):
        """ Retrieves the time delay in s. """
        return self.dev.query(":TIMebase:DELay?")

    def get_time_reference(self):
        """
        Retrieves the time reference.

        Returns:
            str: One of the following time reference positions:
                - 'LEFT'
                - 'CENTER'
                - 'RIGHT'
        """
        return self.dev.query(":TIMebase:REFerence?")

    #######################################################################################
    #                                Triggering                                           #
    #######################################################################################

    def single(self):
        ''' Single Button '''
        self.dev.write(":SINGle")
    
    def get_trigger_event(self):                     # Not used yet
        """
        whether the osci was triggered or not
        return: 
            0   :   No trigger event was registred
            1   :   trigger event was registred
        """
        return int(self.dev.query(':TER?'))  
    
    # ----------------------------------------------- Trigger Type
    def set_trigger_type(self, type):
        """ valid types : EDGE, GLITch, PATTern, SHOLd, TRANsition, TV, SBUS1 """
        valid_types = {"EDGE", "GLITch", "PATTern", "SHOLd", "TRANsition", "TV", "SBUS1"}
        
        if type not in valid_types:
            raise LabscriptError(f"Invalid trigger mode. Valid modes are: {', '.join(valid_types)}")
        
        self.dev.write(f":TRIGger:MODE {type}")

    def get_trigger_type(self):
        """Get the current trigger type."""
        return self.dev.query(":TRIGger:MODE?")

    # ----------------------------------------------- Trigger source
    def set_trigger_source(self, source):
        """
          Valid source : CHANnel<n> , EXTernal , LINE" , WGEN}
          with n = channel number
        """
        try:
            self.dev.write(f":TRIGger:SOURce {source} ")
            if self.verbose:
                print("Done trigger source")
        except Exception as e: 
            raise LabscriptError("trigger_source: "+ e)
        
    def get_trigger_source(self):
        self.trigger_source = self.dev.query(":TRIGger:SOURce?")
        return self.trigger_source
    
    # ----------------------------------------------- Trigger Level
    def set_trigger_level(self, level,unit="V"):
        """ unit : V or mV """
        assert unit in ["V","mV"], LabscriptError("unit must be V or mV")

        """Set the trigger level in V"""
        if self.trigger_source == "EXTernal":
            self.dev.write(f":EXTernal:LEVel {level}{unit}")
            if self.verbose:
                print("Done trigger level EXternal")
        else:
            self.dev.write(f":TRIGger:LEVel {level}{unit}")
            if self.verbose:
                print("Done trigger level")

    def get_trigger_level(self):
        """Get the current trigger level."""
        
        if self.trigger_source == "EXTernal":
            return self.dev.query(":EXTernal:LEVel?")
        else:
            return self.dev.query(":TRIGger:LEVel?")
        
    # ----------------------------------------------- Trigger Edge slope
    def set_trigger_edge_slope(self,slope):
        """
        Args:
            slope : POSitive, NEGative , EITHer , ALTernate
        """
        if self.trigger_type != "EDGE":
            raise LabscriptError("Trigger type must be \"EDGE\" ")
        self.dev.write(f":TRIGger:EDGE:SLOPe {slope}")
        if self.verbose:
                print("Done trigger slope")
    
    def get_trigger_edge_slope(self):
        """
        Returns:
            slope : POSitive, NEGative , EITHer , ALTernate
        """
        return self.dev.query(":TRIGger:EDGE:SLOPe?")
    
    #######################################################################################
    #                            Channel Configurations                                   #
    #######################################################################################

    # ----------------------------------------------- Probe Attenuation
    def set_probe_attenuation(self,attenuation, channel):
        """
        Sets the probe attenuation factor for the selected channel.
        Allowed range: 0.1 -  10000
        """
        try:
            assert ( 0.1<= float(attenuation) <= 1e4)
            self.dev.write(f":CHANnel{channel}:PROBe {attenuation}")
            if self.verbose:
                print("Done probe attenuation")
            
        except Exception as e:
            raise LabscriptError("Probe attenuation ration not in range 0.1 - 10000") 

    def get_probe_attenuation(self,channel):
        return self.dev.query(f":CHANnel{channel}:PROBe?")
    
    # ----------------------------------------------- Display a channel
    def set_channel_display(self,channel,display):
        """"display a channel
        args: 
            channel: str the channel number 
            display: str 0: OFF, 1:ON
        """
        self.dev.write(f":CHANnel{channel}:DISPlay {display}")

    def get_channel_display(self,channel):
        return self.dev.query(f":CHANnel{channel}:DISPlay?")

    # ----------------------------------------------- Displayed channels
    def channels(self, all=True):
        ''' 
            Returns:  dictionary {str supported channels : bool currently displayed }
                      If "all" is False, only visible channels are returned
        '''
        # List with all Channels 
        all_channels = self.dev.query(":MEASure:SOURce?").rstrip().split(",") 

        # We have to change all_channels a little bit for the oscii (e.g CHAN1 -> CHANnel1)
        all_channels = [ch.replace("CHAN", "CHANnel") for ch in all_channels]

        # Create a dictionary {channel : visibility}
        vals = {}
        for index , chan in enumerate(all_channels):
            try:
                visible = bool(int(self.dev.query(f":CHANnel{index + 1 }:DISPlay?")))
            except:
                continue
            if all or visible:
                vals[chan] = visible
        return vals
    
    #######################################################################################
    #                                 Acquiring                                           #
    #######################################################################################

    # ----------------------------------------------- Acquire type
    def set_acquire_type(self,type="NORMal"): 
        ''' 
        The :ACQuire:TYPE command selects the type of data acquisition that is to take
            place. The acquisition types are:

            • NORMal — sets the oscilloscope in the normal mode.

            • AVERage — sets the oscilloscope in the averaging mode. You can set the count
            by sending the :ACQuire:COUNt command followed by the number of averages.
            In this mode, the value for averages is an integer from 1 to 65536. The COUNt
            value determines the number of averages that must be acquired.
            The AVERage type is not available when in segmented memory mode
            (:ACQuire:MODE SEGMented).

            • HRESolution — sets the oscilloscope in the high-resolution mode (also known
            as smoothing). This mode is used to reduce noise at slower sweep speeds
            where the digitizer samples faster than needed to fill memory for the displayed
            time range.
            For example, if the digitizer samples at 200 MSa/s, but the effective sample
            rate is 1 MSa/s (because of a slower sweep speed), only 1 out of every 200
            samples needs to be stored. Instead of storing one sample (and throwing others
            away), the 200 samples are averaged together to provide the value for one
            display point. The slower the sweep speed, the greater the number of samples
            that are averaged together for each display point.

            • PEAK — sets the oscilloscope in the peak detect mode. In this mode,
            :ACQuire:COUNt has no meaning.

            The AVERage and HRESolution types can give you extra bits of vertical resolution.
            See the User's Guide for an explanation. When getting waveform data acquired
            using the AVERage and HRESolution types, be sure to use the WORD or ASCii
            waveform data formats to get the extra bits of vertical resolution. 
        '''
        self.dev.write(":ACQuire:TYPE "+ type)
        if self.verbose:
                print("Done acquire type")

    def get_acquire_type(self):
        return self.dev.query(":ACQuire:TYPE?")
    # ----------------------------------------------- Acquire count
    def set_acquire_count(self,count):
        ''' In averaging and Normal mode, specifies the number of values 
        to be averaged for each time bucket before the acquisition is considered to be
        complete for that time bucket. 
            - count:  2 - 65536.
        ''' 
        if self.acquire_type not in ["HRESolution","PEAK","NORMal" ]:
            self.dev.write(f":ACQuire:COUNT {count}")
            if self.verbose:
                print("Done trigger count")

    def get_acquire_count(self):
        return self.dev.query(":ACQuire:COUNT?")
    # ----------------------------------------------- Acquire source
    def set_waveform_source(self,channel):
        ''' Set the location of the data transferred by WAVeform 
        ARGS:
            channel (str or int): the channel number
        '''
        self.dev.write(f":WAVeform:SOURce {channel}")    
    
    def get_waveform_source(self):
        return self.dev.query(":WAVeform:SOURce?")
    
    #######################################################################################
    #                                 Reading                                             #
    #######################################################################################

    def get_waveform_format(self):
        return self.dev.query(":WAVeform:FORMat?")
    
    # ----------------------------------------------- Waveform Preample
    def get_preample_as_dict(self):
        """
            return dict with the following keys
        keys = [
            "format",       # for BYTE format, 1 for WORD format, 4 for ASCii format; an integer in NR1 format (format set by :WAVeform:FORMat)
            "type",         # 2 for AVERage type, 0 for NORMal type, 1 for PEAK detect type; an integer in NR1 format (type set by :ACQuire:TYPE).
            "points",       # points 32-bit NR1
            "count",        # Average count or 1 if PEAK or NORMal; an integer in NR1 format (count set by :ACQuire:COUNt)
            "xincrement",   # 64-bit floating point NR3>,
            "xorigin"  ,    # 64-bit floating point NR3>,
            "xreference",   # 32-bit NR1>,
            "yincrement",   # 32-bit floating point NR3>,
            "yorigin"  ,    # 32-bit floating point NR3>,
            "yreference",   # 32-bit NR1.
            ]
        """
        keys = ["format","type","points","count","xincrement","xorigin","xreference","yincrement","yorigin","yreference"]
        preamble = self.dev.query(":WAVeform:PREamble?")
        preamble_val = [float(i) for i in preamble.split(",")]
        return dict(zip(keys, preamble_val))

    # ----------------------------------------------- Waveform function (BYTE or WORD(int16))
    def waveform(self, waveform_format="BYTE" ,channel='CHANnel1' ):
        """ 
        returns:  dict 
            * Waveform preample : List, as set by the 'Record length' setting in the 'Acquisition' menu.
            * Times: List of acquired times  
            * Values: List of acquired voltages
        """
        # configure the data type transfer 
        self.set_waveform_source(channel)

        # Sets the data transmission mode for waveform data points. 
                # WORD: formatted data transfers 16-bit data as two bytes. 
                # BYTE: formatted data is transferred as 8-bit bytes.
        if waveform_format in ["WORD", "BYTE"]:
            self.dev.write(f":WAVeform:FORMat {waveform_format}")
            datatype = "H" if waveform_format == "WORD" else "B"
            
            if self.verbose:
                print(f"Done Waveform {waveform_format}")
        else : 
            raise KeyError("Waveform format must be WORD or BYTE")


        # transfer the data and format into a sequence of strings
        raw = self.dev.query_binary_values(
            ':WAVeform:DATA?',                
            datatype=datatype,       # 'B' and 'H' are for unassigned , if you want signed use h and b 
            #is_big_endian=True,     # In case we shift to signed
            container=np.array
            )
        
        # Create a dictionary of the waveform preamble
        wfmp = self.get_preample_as_dict()

        # (see Page 667 , Keysight manual for programmer )
        n = np.arange(wfmp['points'] ) 
        t = (    n  - wfmp['xreference']) * wfmp['xincrement'] + wfmp['xorigin']  # time    = [( data point number - xreference) * xincrement] + xorigin
        data = (   raw - wfmp['yreference']) * wfmp['yincrement'] + wfmp['yorigin']  # voltage = [(    data value    - yreference)  * yincrement] + yorigin  

        return wfmp, t, data


    def waveform_ascii(self):
        self.dev.write(":WAVeform:FORMat ASCii") 
        data_ascii = self.dev.query(":WAVeform:DATA?")
        data = np.array([float(x) for x in data_ascii.split(", ")[1:]])
        len_data = len(data)
        len_x_achse =  self.get_time_range()
        t = np.linspace(0,len_x_achse , len_data)
        wfmp = self.get_preample_as_dict()
        return wfmp, t, data


    #######################################################################################
    #                               Wave Generator                                        #
    #######################################################################################
    
    def wgen_on(self, on = True):
        ''' Wave generator'''
        if on:
            self.dev.write(":WGEN:OUTPut 1")  # 1 is on 
        else:
            self.dev.write(":WGEN:OUTPut 0")  # 0 is off

    def set_wgen_freq(self, freq = 1):
        """ in Hz """        
        self.dev(f":WGEN:FREQuency {freq}")

    def set_wgen_form(self, form = "SQUare" ):
        """
        Possible forms:
            {SINusoid | SQUare | RAMP | PULSe | NOISe | DC}
        """
        self.dev(f":WGEN:FUNCtion {form}")

    def set_wgen_voltage(self, voltage= 1):
        "in V , possible 1mv"
        self.dev(f":WGEN:VOLTage {voltage}")

    def set_wgen_high(self, voltage_high= 1):
        """
        in V : High level of the signal
        """
        self.dev(f":WGEN:VOLTage:HIGH {voltage_high}")

    def set_wgen_low(self, voltage_low= 0):
        """
        in V : Low level of the signal
        """
        self.dev(f":WGEN:VOLTage:LOW {voltage_low}")

