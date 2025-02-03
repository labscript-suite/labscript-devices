import pyvisa
import numpy as np
import time

"""
Using the Oscilloscope requires 3 important steps 

    * Initialsiation : which is setting up the osci for the desired measure
    * Acquiring : the osci aquires the measurement and saves them in its memory
    * Analysing : after finishing the measurement, we can display or transfer the data to the Pc

    ===== > This code is therfore organized after the above mentionned three blocks 


 To Improve:
  -  connecting to the oscilloscope should not be implemented here
  -  passing the properties should be more flexible (example NI_DAQmx)
  -  Implemente  other aquiring  modes  -- Average . Normal , Peak 
  -  Investigate what is better signed or unsigned bits
"""

# Model DS01202G
class KeysightScope:
    def __init__(self, addr='USB?*::INSTR', 
                 timeout =5):
        # Connecting to the osci
        rm = pyvisa.ResourceManager()
        devs = rm.list_resources(addr)
        assert len(devs), "PyVisa didn't find any connected devices matching " + addr
        self.dev = rm.open_resource(devs[0])
        self.idn = self.dev.query('*IDN?')
        print(f"The scope {self.idn} was successfully initialized")

        # Basic Visa commands (if Visa works on the osci, then these will work)
        self.read = self.dev.read           # class method
        self.write = self.dev.write         # class method
        self.query = self.dev.query         # class method

        # Setting the osci properties       
        # --------------------------------- Device properties (Fix)
        self.band_width = 70e6              # 70 MHz
        self.sampling_rate = 2*10e9         # 2GSa/s
        self.max_memory = 1e6               # 1Mpts
        self.max_update_rate = 5e4          # 50,000 waveforms/second update rate.

        # Setting the osci configurations
        self.dev.timeout = 1000 * timeout   # convert in seconds

        # INIT: Preset and wait for operations to complete
        self.dev.write("*RST")              # An instrument control script should start with a *RST command.
        self.dev.query("*OPC?")             # Synchronization: Waits until previous commands is done before moving forward in the script
        self.autoscale()

        # ############################################################# in progress 
        # Measurement setup variablees
        vRange = 2
        tRange = 500e-9
        trigerLevel = 0
        ch = 1  

        GENERAL_TIMEOUT = 5000  # General I/O timeout (ms)
        TRIGGER_TIMEOUT = 60000  # Max time to wait for a trigger (ms) for *OPC? method

        # Prevent excessive queries by adding a delay in seconds:
        POLLING_INTERVAL = 0.1  # (seconds)

 

    #######################################################################################
    #                               Initialisation                                        #
    #######################################################################################
    def set_acquire_state(self, running=True):
        '''RUN / STOP '''
        self.dev.write(':RUN' if running else 'STOP')

    def abort(self):
        self.dev.write(':STOP')
        return True

    def get_acquire_state(self):        # In other words , is it running ? 
        """Determine if the oscilloscope is running.
        Returns: ``True`` if running, ``False`` otherwise
        """
        reg = int(self.dev.query(':OPERegister:CONDition?')) # The third bit of the operation register is 1 if the instrument is running
        return int((reg & 8) == 8)

    def digitize(self):
        ''' Specialized RUN command. 
                        acquires a single waveforms according to the settings of the :ACQuire commands subsystem.
                        When the acquisition is complete, the instrument is stopped.
        '''
        self.dev.query(":DIGitize")

    def autoscale(self):
        self.dev.write(":AUToscale")

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
    
    def shutdown(self):
        """Closes VISA connection to device."""
        self.dev.close()

    def get_trigger_event(self):
        """
        whether the osci was triggered or not
        return: 
            0   :   No trigger event was registred
            1   :   trigger event was registred
        """
        return int(self.dev.query(':TER?'))  
    
    def clear_status(self):
        """
        clears:     the status data structures, 
                    the device-defined error queue,
                    and the Request-for-OPC flag
        """
        self.dev.write("*CLS")
    
    # ------------------------------------- TRiggering (IN PROGRESS) 

    def single(self):
        ''' Single Button '''
        self.dev.query(":SINGle")

    def set_trigger_mode(self):                     # (FUTUR) add more trigger types
        self.dev.write("trigger:mode edge")         # change capitalizations for commands for the next 2 functions

    def set_trigger_level(self,channel, triggerLevel):
        self.dev.write(f"trigger:level channel{channel}, {triggerLevel}")

    # ----------------------------------------------- Voltage   # (TDOO) Here Error Hanedling 

    def set_t_range(self,channel,tRange):
        """ for all 10 div  """
        self.dev.write(f"timebase:range{tRange}")

    def set_v_square(self,channel, volt_square, unit="V"):          
        if unit =="V":
            self.dev.write(f":CHANnel{channel}:RANGe {volt_square*8}")
        elif unit =="mV":
            self.dev.write(f":CHANnel{channel}:RANGe {volt_square*8}mV")

    def set_v_scale(self, scale_value):
        """ scale_value ::= voltage/div in volt in NR3 format """
        self.dev.write(f":CHANnel1:SCALe {scale_value}")
        

    # ----------------------------------------------- Time  # (TDOO) Here Error Hanedling 

    def set_t_square(self, time_square):
        """in seconds """
        self.dev.write(f":TIMebase:RANGe {time_square*10}")

    def get_t_scale(self):
        self.dev.write(":TIMebase:SCALe?")

    def set_t_scale(self,scale_value):
        """
        scale_value ::= time/div in seconds in NR3 format
        """
        self.dev.write(f":TIMebase:SCALe {scale_value}")

    
    #######################################################################################
    #                                 Acquiring                                           #
    #######################################################################################
    #
    def set_aquire_type(self,type="NORMal"): 
        ''' 
        There are 4 aquire types for this:
            * NORMal      : 
            * AVERage     : You can set the count by sending the :ACQuire:COUNt command followed by the number of averages. 
                            In this mode, the value for averages is an integer from 1 to 65536. 
                            The COUNt value determines the number of averages that must be acquired.
            * HRESolution : reduce noise at slower sweep speeds where 
                            the digitizer samples faster than needed to fill memory for the displayed time range. 
            * PEAK        : PEAK  
        '''
        self.dev.write(":ACQuire:TYPE "+ type)

    
    # ----------------------------------- Waveform
    def set_waveform_source(self,channel):
        self.dev.write(':WAVeform:SOURce ' + channel)    # set the location of the data transferred by WAVeform?
    
    #######################################################################################
    #                                 Reading                                             #
    #######################################################################################
    def get_xIncrement(self):   # (in progress)
        return float(self.dev.query("waveform:xincrement?"))
    
    def get_xOrigin(self):      # (in progress)
        return float(self.dev.query("waveform:xincrement?"))

    def get_yIncrement(self):   # (in progress)
        return float(self.dev.query("waveform:xincrement?"))

    def get_yOrigin(self):      # (in progress)
        return float(self.dev.query("waveform:xincrement?"))

        

    def waveform(self, channel='CHANnel1', int16=False):
        """ 
        returns:  dict 
            * Waveform preample : List, as set by the 'Record length' setting in the 'Acquisition' menu.
            * Times: List of acquired times  
            * Values: List of acquired voltages

        """
        # configure the data type transfer 
        self.set_waveform_source(self,channel)           # set the location of the data transferred by WAVeform?
    
        # transfer the data and format into a sequence of strings
        raw = self.dev.query_binary_values(':WAVeform:DATA?',                
            datatype='H' if int16 else 'B',                                  # 'B' and 'H' are for unassigned , if you want signed use h and b 
            #is_big_endian=True,                                             # In case we shift to signed
            container=np.array
            )
        
        # Create a dictionary for the preamble 
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

        # Get the Preamble 
        preamble = self.dev.query(":WAVeform:PREamble?")
        preamble_val = [float(i) for i in preamble.split(",")]

        # create a dictionary of the waveform preamble
        wfmp = dict(zip(keys, preamble_val))

        # (see Page 667 , Keysight manual for programmer )
        n = np.arange(wfmp['points'] ) 
        t = (    n  - wfmp['xreference']) * wfmp['xincrement'] + wfmp['xorigin']  # time    = [( data point number - xreference) * xincrement] + xorigin
        y = (   raw - wfmp['yreference']) * wfmp['yincrement'] + wfmp['yorigin']  # voltage = [(    data value    - yreference)  * yincrement] + yorigin  

        print(y,t)
        return wfmp, t, y



    #######################################################################################
    #                                 Misc                                                #
    #######################################################################################
    # Works fine 
    def set_date_time(self, verbose=False):
        if verbose:
            print('Setting date and time...')
        self.sendrecv('DATE "' + time.strftime('%Y-%m-%d',time.localtime()) + '"') # set the date
        self.sendrecv('TIME "' + time.strftime('%H:%M:%S',time.localtime()) + '"') # set the time


    def close(self):
        self.dev.close()

    def lock(self, verbose=False):
        if verbose:
            print('Locking front panel')
        self.dev.write(':SYSTem:LOCK 1')

    def unlock(self, verbose=False):
        if verbose:
            print('Unlocking front panel')
        self.dev.write(':SYSTem:LOCK 0')

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
        """
        in Hz
        """        
        self.dev(f":WGEN:FREQuency {freq}")

    def set_wgen_form(self, form = "SQUare" ):
        """
        Possible forms:
            {SINusoid | SQUare | RAMP | PULSe | NOISe | DC}
        """
        self.dev(f":WGEN:FUNCtion {form}")

    def set_wgen_voltage(self, voltage= 1):
        self.dev(f":WGEN:VOLTage {voltage}")

    def set_wgen_high(self, voltage_high= 1):
        """
        in V : High level of the signal
        """
        self.dev(f":WGEN:VOLTage:HIGH {voltage_high}")

    def set_wgen_high(self, voltage_low= 0):
        """
        in V : Low level of the signal
        """
        self.dev(f":WGEN:VOLTage:LOW {voltage_low}")


  
#####################################################################################################
#####################################################################################################
#####################################################################################################
#####################################################################################################
    # Not Sure we will use the png option
    def get_screenshot(self, verbose=False):
        pass
        # if verbose:
        #     print('Downloading screen image...')

        # self.dev.write('SAVE:IMAG:FILEF PNG')
        # self.dev.write('HARDCOPY START')
        # return self.dev.read_raw(None)

    def save_screenshot(self, filepath, verbose=False):
        pass
        # if verbose:
        #     print('Saving screen image...')
        # data = self.get_screenshot()
        # with open(filepath, 'wb') as f:
        #     f.write(data)

    


## uncomment to test
if __name__ == '__main__':

    scope = KeysightScope(addr='USB?*::INSTR', timeout=5)


    # Works perfect
    def transition_to_manual():

        channels = scope.channels()
        data_dict = {}           # Create Dict chanel - data
        vals = {}
        wtype = [('t', 'float')]     
        print('Downloading...')

        for ch, enabled in channels.items():
            if enabled:
                data_dict[ch], t, vals[ch] = scope.waveform(
                    ch,
                    int16= False                               # THis was : self.scope_params.get('int16', False),           
                )
                wtype.append((ch, 'float'))

        # Collect all data in a structured array
        data = np.empty(len(t), dtype=wtype)
        data['t'] = t
        for ch in vals:
            data[ch] = vals[ch]
        print(data)

    def transition_to_buffered():
        scope.unlock()
        scope.write(':ACQuire:TYPE AVERage')
        scope.set_acquire_state(True)
        return {}
    


    transition_to_manual()
    #transition_to_buffered()




    # to improve first connection
    # manufacturer, model, sn, revision = self.scope.idn.split(',')
    # #assert manufacturer.lower() == 'tektronix'      
    # #"Device is made by {:s}, not by Tektronix, and is actually a {:s}".format(
    #  #   manufacturer, model
    # #)
    # print('Connected to {} (SN: {})'.format(model, sn))