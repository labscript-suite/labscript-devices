import pyvisa
import numpy as np
import time

"""
    --init-  -- yes
    channels() -- no 
    rest -- (to test)
"""


"""
 zu verbessern, CASE HAndling for other aquiring and acquisation modes

"""

class KeysightScope:
    def __init__(self, addr='USB?*::INSTR', 
                 timeout =3, termination='\n'):
        rm = pyvisa.ResourceManager()
        devs = rm.list_resources(addr)

        assert len(devs), "PyVisa didn't find any connected devices matching " + addr

        self.dev = rm.open_resource(devs[0])
        self.dev.timeout = 1000 * timeout
        self.dev.read_termination = termination
        self.idn = self.dev.query('*IDN?')
        self.read = self.dev.read # class method
        self.write = self.dev.write # class method
        self.query = self.dev.query # class method
        print(f"The scope {self.idn} was successfully initialized")


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def channels_old(self, all=True):
        """Return a dictionary of the channels supported by this scope and whether they are currently displayed.
        Includes REF and MATH channels if applicable. If "all" is False, only visible channels are returned"""
        # want to enable HEAD to get channel names as well
        prev = self.dev.query('HEAD?') 
        self.dev.write('HEAD 1')
        # determine the device capabilities and enabled status
        resp = self.dev.query('SEL?').rsplit(':',1)[1] 
        # reset HEAD
        self.dev.write('HEAD '+prev)
        # create a dict from the response
        vals = {}
        for x in resp.split(';'):               
            name, val = x.rsplit(' ',1)
            if name[0] == ':':
                name = name.rsplit(':',1)[1]     
            try:
                visible = bool(int(val))            
            except:
                continue
            if all or visible:
                vals[name] = visible
        return vals
    

#####################################################################################################
#####################################################################################################
#####################################################################################################
#####################################################################################################
#####################################################################################################

    # ------------------------------------- NEW FOR KEYSIGHT
    def channels(self, all=True):
        """Return a dictionary of the channels supported by this scope and whether they are currently displayed.
        If "all" is False, only visible channels are returned"""

        all_channels = self.dev.query(":MEASure:SOURce?").rstrip().split(",") # List with all Channels 
        vals = {}
        for index , chan in enumerate(all_channels):
            try:
                visible = bool(int(self.dev.query(f":CHANnel{index + 1 }:DISPlay?")))
            except:
                continue
            if all or visible:
                vals[chan] = visible
        return vals

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def waveform_old(self, channel='CH1', preamble_string='WFMO', int16=False):
        """Download the waveform of the specified channel from the oscilloscope. All
        acquired points are downloaded, as set by the 'Record length' setting in the
        'Acquisition' menu. A dictionary of waveform formatting parameters is returned
        in addition to the times and values.
        """
        # configure the data transfer
        self.dev.write('DAT:SOU ' + channel)             # set the location of the data transferred by CURVe?
        self.dev.write('DAT:ENC RIB')                    # tranfer the waveform in binary format (signed, MSB)
        if int16:
            self.dev.write(preamble_string + ':BYT_N 2')               # use 16-bit integers (but only return every second pt)
        else:
            self.dev.write(preamble_string + ':BYT_N 1')               # use 8-bit integers
        record_length = int(self.dev.query('HOR:RECO?')) # determine how many points exist
        self.dev.write('DAT:START ' + '1')               # set the first data point to transfer
        self.dev.write('DAT:STOP ' + str(record_length)) # set the last data point to transfer

        # transfer the data and format into a sequence of strings
        raw = self.dev.query_binary_values('CURV?', 
            datatype='i' if int16 else 'b', 
            is_big_endian=True,
            container=np.array
            )

        # create a dictionary for the header information
        keys = [
            'BYT_NR',                                 # data width for the outgoing waveform
            'BIT_NR',                                 # number of bits per waveform point (8 or 16)
            'ENCDG',                                  # type of encoding (ASCII or binary)
            'BN_FMT',                                 # format of binary data (redundant for ASCII transfer) 
            'BYT_OR',                                 # first transmitted byte of binray data (LSB or MSB) 
            'NR_PT',                                  # number of points transmitted in response to a CURVe? query 
            'WFID',                                   # acquisition parameters 
            'PT_FMT',                                 # point format: {ENV: min/max pairs, Y: single points}
            'XINCR',                                  # horizontal increment
            'PT_OFF',                                 # trigger offset
            'XZERO',                                  # time coordinate of the first point
            'XUNIT',                                  # horizontal units
            'YMULT',                                  # vertical scale factor per digitizing level
            'YZERO',                                  # vertical offset
            'YOFF',                                   # vertical position in digitizing levels
            'YUNIT'                                   # vertical units
            ]

        # wfstr = self.dev.query(preamble_string + '?').split(';')    # waveform transmission and formatting parameters
        self.dev.write(';:'.join([preamble_string + ':' + k  + '?' for k in keys]))
        wfstr = self.dev.read().split(';')

        # create a dictionary of the waveform preamble
        wfmp = {}
        for key, x in zip(keys, wfstr):
            x = str(x)
            if x[0] == '"':                             # is it an enclosed string?
                x = x.split('"')[1]
            elif str.isdigit(x):                        # is it an integer
                x = int(x)
            else:
                try: x = float(x)                       # try floating point number
                except: pass
            wfmp[key] = x

        # return the times and voltages
        n = np.arange(0, wfmp['NR_PT'] / wfmp['BYT_NR'])
        t = wfmp['BYT_NR'] * wfmp['XINCR'] * (n - wfmp['PT_OFF']) + wfmp['XZERO']
        y = wfmp['YMULT'] * (raw - wfmp['YOFF']) + wfmp['YZERO']
        return wfmp, t, y
    
#####################################################################################################
#####################################################################################################
#####################################################################################################
#####################################################################################################
#####################################################################################################


    def waveform(self, channel='CHANnel1', int16=False):
        """ as set by the 'Record length' setting in the
        'Acquisition' menu.
        Return:  Dictionary : waveform formatting parameters , times, values.

        TO TEST = int16 True --> :WAVeform:FORMat WORD
        """

        # configure the data transfer
        self.dev.write(':WAVeform:SOURce ' + channel)    # set the location of the data transferred by WAVeform?
    
        if int16:
            self.dev.write(':WAVeform:FORMat WORD')      # use 16-bit integers 
                                                         # To TEST: 
                                                         # --- Tekscope : but only return every second pt , KEysight too ??
                                                         # --- gpt sagt das ist besser  aslbinary
        else:
            self.dev.write(':WAVeform:FORMat BYTE')      # use 8 -bit integers    



        record_length = int(self.dev.query(':WAVeform:POINts?')) # determine how many points exist

        # transfer the data and format into a sequence of strings
        raw = self.dev.query_binary_values(':WAVeform:DATA?',                # TO TEST INT 16 ---> WORD
            datatype='i' if int16 else 'b', 
            is_big_endian=True,
            container=np.array
            )
        
        # Create a dictionary for the preamble 
        keys = [
            " format",       # for BYTE format, 1 for WORD format, 4 for ASCii format; an integer in NR1 format (format set by :WAVeform:FORMat)
            " type",         # 2 for AVERage type, 0 for NORMal type, 1 for PEAK detect type; an integer in NR1 format (type set by :ACQuire:TYPE).
            " points",       # points 32-bit NR1
            " count",        # Average count or 1 if PEAK or NORMal; an integer in NR1 format (count set by :ACQuire:COUNt)
            " xincrement",   # 64-bit floating point NR3>,
            " xorigin"  ,    # 64-bit floating point NR3>,
            " xreference",   # 32-bit NR1>,
            " yincrement",   # 32-bit floating point NR3>,
            " yorigin"  ,    # 32-bit floating point NR3>,
            " yreference",   # 32-bit NR1.
            ]

        
        # Get the Preamble 
        preamble = scope.query(":WAVeform:PREamble?")
        wfstr = [float(i) for i in preamble.split(",")]

        # create a dictionary of the waveform preamble
        wfmp = dict(zip(keys, wfstr))

        # return the times and voltages
        n = np.arange(0, wfmp['NR_PT'] / wfmp['BYT_NR'])
        t = wfmp['BYT_NR'] * wfmp['XINCR'] * (n - wfmp['PT_OFF']) + wfmp['XZERO']   # time = [(data point number - xreference) * xincrement] + xorigin
        y = wfmp['YMULT'] * (raw - wfmp['YOFF']) + wfmp['YZERO']                    # voltage = [(data value - yreference) * yincrement] + yorigin  (see Page 667 , Keysight manual for programmer )
        return wfmp, t, y
          
          
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def get_screenshot(self, verbose=False):
        if verbose:
            print('Downloading screen image...')
        self.dev.write('SAVE:IMAG:FILEF PNG')
        self.dev.write('HARDCOPY START')
        return self.dev.read_raw(None)

    def save_screenshot(self, filepath, verbose=False):
        if verbose:
            print('Saving screen image...')
        data = self.get_screenshot()
        with open(filepath, 'wb') as f:
            f.write(data)

    def set_date_time(self, verbose=False):
        if verbose:
            print('Setting date and time...')
        self.sendrecv('DATE "' + time.strftime('%Y-%m-%d',time.localtime()) + '"') # set the date
        self.sendrecv('TIME "' + time.strftime('%H:%M:%S',time.localtime()) + '"') # set the time

    def lock(self, verbose=False):
        if verbose:
            print('Locking front panel')
        self.dev.write('LOCk ALL')

    def unlock(self, verbose=False):
        if verbose:
            print('Unlocking front panel')
        self.dev.write('LOCk NONE')

    def get_acquire_state(self):
        reponse = self.dev.query('ACQ:STATE?')
        return int(response)

    def set_acquire_state(self, running=True):
        self.dev.write('ACQ:STATE ' + 'START' if running else 'STOP')

    def close(self):
        self.dev.close()




if __name__ == '__main__':
    # scope = KeysightScope(addr='TCP?*::INSTR', timeout=10)
    scope = KeysightScope(addr='USB?*::INSTR', timeout=10)
  
    print( scope.channels() )
  
    # Testings 
    # print("channels ", scope.channels()) 

    def transition_to_manual():
        chans = scope.channels()

        wfmp = {}
        vals = {}
        wtype = [('t', 'float')]
        
        print('Downloading...')

        for ch, enabled in channs.items():
            if enabled:
                wfmp[ch], t, vals[ch] = self.scope.waveform(
                    ch,
                    int16=self.scope_params.get('int16', False),
                    preamble_string=self.preamble_string,
                )
                wtype.append((ch, 'float'))
                print(wfmp[ch]['WFID'])

        # Collate all data in a structured array
        data = np.empty(len(t), dtype=wtype)
        data['t'] = t
        for ch in vals:
            data[ch] = vals[ch]
