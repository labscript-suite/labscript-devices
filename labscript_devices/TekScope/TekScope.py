import pyvisa
import numpy as np
import time

class TekScope:
    def __init__(self, addr='USB?*::INSTR', 
                 timeout=1, termination='\n'):
        rm = pyvisa.ResourceManager()
        devs = rm.list_resources(addr)
        assert len(devs), "pyvisa didn't find any connected devices matching " + addr
        self.dev = rm.open_resource(devs[0])
        self.dev.timeout = 1000 * timeout
        self.dev.read_termination = termination
        self.idn = self.dev.query('*IDN?')
        self.read = self.dev.read
        self.write = self.dev.write
        self.query = self.dev.query

    def channels(self, all=True):
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

    def waveform(self, channel='CH1', preamble_string='WFMO', int16=False):
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
    scope = TekScope(addr='TCP?*::INSTR', timeout=10)
    manufacturer, model, sn, revision = scope.idn.split(',')
    assert manufacturer.lower() == 'tektronix'
    "Device is made by {:s}, not by Tektronix, and is actually a {:s}".format(manufacturer, model)
    print('Connected to {} (SN: {})'.format(model, sn))

