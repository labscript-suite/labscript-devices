#####################################################################
#                                                                   #
# RFblaster.py                                                      #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from labscript_utils.setup_logging import setup_logging
from blacs.tab_base_classes import Worker


                
class MultiPartForm(object):
    """Accumulate the data to be used when posting a form."""
    def __init__(self):
        self.form_fields = []
        self.files = []
    
    def get_content_type(self):
        return b'multipart/form-data; boundary=%s' % self.boundary

    def add_field(self, name, value):
        """Add a simple field to the form data."""
        self.form_fields.append( (name, value) )

    def add_file_content(self, fieldname, filename, body, mimetype=None):
        import mimetypes
        if not isinstance(body, bytes):
            raise TypeError('body must be bytes')
        if mimetype is None:
            mimetype = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        self.files.append((fieldname, filename, mimetype, body))


    
class RFBlasterWorker(Worker):
    def init(self):
        exec('from numpy import *', globals())
        global h5py; import labscript_utils.h5_lock, h5py
        global re; import re
        self.timeout = 10   # How long do we wait until we assume that the RFBlaster is dead? (in seconds)
        self.retries = 3    # Retry attempts before (a) giving up, or (b) attempting to restart kloned (uniform timeout)
        p = re.compile('http://([0-9.]+):[0-9]+')
        m = p.match(self.address)
        self.ip = m.group(1)
        self.netlogger = setup_logging('rfBlaster_%s' % self.ip)
        self.netlogger.info('init: Started logging')
        self.http_request() # See if the RFBlaster answers
        self._last_program_manual_values = {}

    def restart_kloned(self, respawn_netcat=True):
        import socket, time
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        self.netlogger.info('restart_kloned: Connecting to %s...', self.ip)
        s.connect((self.ip, 8009))
        self.netlogger.info('restart_kloned: Connected!')
        if respawn_netcat:
            self.netlogger.info('restart_kloned: Respawning netcat...')
            s.sendall(b'nohup nc -l -p 8009 -e /bin/sh &')
            time.sleep(0.5)
        self.netlogger.info('restart_kloned: Trying to start/restart kloned...')
        s.sendall(b'./startup/klone_start.sh')
        time.sleep(0.5)
        s.shutdown(socket.SHUT_WR)
        self.netlogger.info('restart_kloned: Finished. Closing socket.')
        s.close()

    def program_manual(self,values):
        self._last_program_manual_values = values
        form = MultiPartForm()
        for i in range(self.num_DDS):
            # Program the frequency, amplitude and phase
            form.add_field("a_ch%d_in"%i,str(values['dds %d'%i]['amp']*values['dds %d'%i]['gate']))
            form.add_field("f_ch%d_in"%i,str(values['dds %d'%i]['freq']*1e-6)) # method expects MHz
            form.add_field("p_ch%d_in"%i,str(values['dds %d'%i]['phase']))
        form.add_field("set_dds", "Set device")
        return_vals = self.get_web_values(self.http_request(form))
        return return_vals
        
    def transition_to_buffered(self,device_name,h5file,initial_values,fresh):
        with h5py.File(h5file,'r') as hdf5_file:
            group = hdf5_file['devices'][device_name]
            # Strip out the binary files and submit to the webserver
            form = MultiPartForm()
            self.final_values = {}
            finalfreq = zeros(self.num_DDS)
            finalamp = zeros(self.num_DDS)
            finalphase = zeros(self.num_DDS)
            for i in range(self.num_DDS):
                #Find the final value from the human-readable part of the h5 file to use for
                #the front panel values at the end
                self.final_values['dds %d'%i] = {'freq':group['TABLE_DATA']["freq%d"%i][-1],
                                                 'amp':group['TABLE_DATA']["amp%d"%i][-1]*100,
                                                 'phase':group['TABLE_DATA']["phase%d"%i][-1],
                                                 'gate':True
                                                }
                data = group['BINARY_CODE/DDS%d'%i][()]
                form.add_file_content("pulse_ch%d"%i, "output_ch%d.bin"%i, data)
                
        form.add_field("upload_and_run", "Upload and start")
        self.http_request(form)
        return self.final_values
                 
    def abort_transition_to_buffered(self):
        # TODO: untested (this is probably wrong...)
        form = MultiPartForm()
        #tell the rfblaster to stop
        form.add_field("halt","Halt execution")
        self.http_request(form)
        return True
    
    def abort_buffered(self):
        form = MultiPartForm()
        # Tell the rfblaster to stop
        form.add_field("halt", "Halt execution")
        self.http_request(form)
        return True
     
    def transition_to_manual(self):
        # TODO: check that the RF blaster program is finished?
        return True
     
    def http_request(self, form=None): 
        """Make a HTTP request to the RFBlaster, optionally submitting a form"""
        import requests
        from urllib.request import urlopen, Request
        from urllib.error import URLError, HTTPError 
    
        self._connection_attempt = 1
        self._kloned_attempted = False
        response = None
        while not response:
            try:
                self.netlogger.info('Connection attempt %i.', self._connection_attempt)
                if form is not None:
                    # For some reason the MultiPartForm object stored form_fields as a list of key,value tuples...
                    # ... rather than a dict. No matter. it seems requests sucks this up anyway.
                    # However we need to rearrange the file data into a nested tuple for requests. No big deal:
                    filelist = [(field_name, (filename, bytes(body), content_type)) for field_name, filename, content_type, body in form.files]
                    r = requests.post(self.address, data=form.form_fields, files=filelist) # Needs to actually send the form
                else:
                    r = requests.get(self.address)
                r.raise_for_status() 
                self.netlogger.info('Connected!')
                break
            except (URLError, HTTPError, TimeoutError, ConnectionError, requests.exceptions.RequestException) as e:
                self.netlogger.warning('%s', e)
                if self._connection_attempt < self.retries:
                    self.netlogger.info('Connection failed. Trying again (%i more attempts remain).', self.retries - self._connection_attempt)
                    self._connection_attempt += 1
                elif not self._kloned_attempted:
                    self._kloned_attempted = True
                    self.restart_kloned()
                    self._connection_attempt = 1
                else:
                    self.netlogger.error('%s', e)   
                    raise e
        return r.text

    def get_web_values(self, page): 
        import re
        # Prepare regular expressions for finding the values:
        search = re.compile(r'name="([fap])_ch(\d+?)_in"\s*?value="([0-9.]+?)"')
        webvalues = re.findall(search, page)
        
        register_name_map = {'f': 'freq', 'a': 'amp', 'p': 'phase'}
        newvals = {}
        for i in range(self.num_DDS):
            newvals['dds %d'%i] = {}
        for register,channel,value in webvalues:
            newvals['dds %d'%int(channel)][register_name_map[register]] = float(value)
        for i in range(self.num_DDS):
            if 'dds %d'%i in self._last_program_manual_values and newvals['dds %d'%i]['amp'] == 0:
                newvals['dds %d'%i]['gate'] = self._last_program_manual_values['dds %d'%i]['gate']
            else:
                newvals['dds %d'%i]['gate'] = True
                
            newvals['dds %d'%i]['freq'] *= 1e6 # BLACS expects it in the base unit (Hz)
            
            # if the gate is off, keep the front panel amplitude
            if not newvals['dds %d'%i]['gate']:
                newvals['dds %d'%i]['amp'] = self._last_program_manual_values['dds %d'%i]['amp']
            
        return newvals
    
    def check_remote_values(self):
        # Read the webserver page to see what values it puts in the form
        return self.get_web_values(self.http_request())
        
    def shutdown(self):
        # TODO: implement this?
        pass
