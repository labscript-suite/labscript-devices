import time
import numpy as np
from blacs.tab_base_classes import Worker
import labscript_utils.properties

class TekScopeWorker(Worker):
    def init(self):
        global h5py; import labscript_utils.h5_lock, h5py
        global TekScope
        from .TekScope import TekScope
        self.scope = TekScope(self.addr, termination=self.termination)
        manufacturer, model, sn, revision = self.scope.idn.split(',')
        assert manufacturer.lower() == 'tektronix'
        "Device is made by {:s}, not by Tektronix, and is actually a {:s}".format(manufacturer, model)
        print('Connected to {} (SN: {})'.format(model, sn))

    def transition_to_buffered(self, device_name, h5file, front_panel_values, refresh):
        self.h5file = h5file  # We'll need this in transition_to_manual
        self.device_name = device_name
        with h5py.File(h5file, 'r') as hdf5_file:
            print('\n' + h5file)
            self.scope_params = scope_params = labscript_utils.properties.get(
                hdf5_file, device_name, 'device_properties')
            self.scope.dev.timeout = 1000 * self.scope_params.get('timeout', 5)
            # hdf5_file['devices'][device_name].attrs.create('some name', some_value, dtype='some_type')

        self.scope.unlock()
        self.scope.set_acquire_state(True)
        # TODO: Make per-shot acquisition parameters and channels configurable here
        self.scope.write('ACQUIRE:MODE SAMPLE')
        self.scope.write('ACQUIRE:STOPAFTER SEQUENCE')
        self.scope.write('ACQUIRE:STATE RUN')
        return {}

    def transition_to_manual(self):
        channels = self.scope.channels()
        wfmp = {}
        vals = {}
        wtype = [('t', 'float')]
        print('Downloading...')
        for ch, enabled in channels.items():
            if enabled:
                wfmp[ch], t, vals[ch] = self.scope.waveform(ch, 
                        int16=self.scope_params.get('int16', False),
                        preamble_string=self.preamble_string)
                wtype.append((ch, 'float'))
                print(wfmp[ch]['WFID'])

        # Collate all data in a structured array
        data = np.empty(len(t), dtype=wtype)
        data['t'] = t
        for ch in vals:
            data[ch] = vals[ch]

        # Open the file after download so as not to hog the file lock
        with h5py.File(self.h5file, 'r+') as hdf_file:
            grp = hdf_file.create_group('/data/traces')
            print('Saving traces...')
            dset = grp.create_dataset(self.device_name, data=data)
            dset.attrs.update(wfmp[ch])
        print('Done!')
        return True

    def program_manual(self, values):
        return values

    def abort(self):
        print('aborting!')
        # self.scope.write('*RST')
        return True

    def abort_buffered(self):
        print('abort_buffered: ...')
        return self.abort()

    def abort_transition_to_buffered(self):
        print('abort_transition_to_buffered: ...')
        return self.abort()