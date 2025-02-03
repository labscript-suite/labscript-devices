import numpy as np
import os
import labscript_utils.h5_lock
import h5py
from zprocess import rich_print

from blacs.tab_base_classes import Worker
import labscript_utils.properties
import matplotlib.pyplot as plt

BLUE = '#66D9EF'
PURPLE = '#AE81FF'
GREEN = '#A6E22E'
GREY = '#75715E' 

class KeysightScopeWorker(Worker):
    def init(self):

        # we migrate osci related functions to a separate class
        global KeysightScope
        from .KeysightScope import KeysightScope
        self.scope = KeysightScope()

        # Buffered/ Manuel relevant flags
        self.buffered_mode = False
        self.acquired_data = None      
        self.h5_file = None

        # (FUTUR) Goal: continuous data aquisation, Example: NI_DAQmxAcquisitionWorker(Worker):
        self.buffered_chans = None
        self.buffered_rate = None     

           

    def transition_to_buffered( self, device_name, h5file, front_panel_values, refresh):
        self.logger.debug('transition_to_buffered')

        self.h5file = h5file                                                    
        self.device_name = device_name

        # Store the initial values in case we have to abort and restore them:
        self.initial_values =  front_panel_values

        # Store the final values to for use during transition_to_static:
        self.final_values = {}
        # Store some parameters for saving data later
        self.h5_file = h5file               # We'll need this in transition_to_manual
        self.device_name = device_name



        with h5py.File(h5file, 'r') as hdf5_file:
            self.scope_params = labscript_utils.properties.get(
                hdf5_file, device_name, 'device_properties'
            )
            
            self.scope.dev.timeout = 1000 * self.scope_params.get('timeout', 5)   # This line -- Why ? 

        # Locking the front Buttons of the osci during buffered mode
        #self.scope.lock()

        # Run : True // Stop: : False
        #self.scope.set_acquire_state(True)
        
        #self.scope.query(":TRIGger:SWEep NORMal")
        #self.scope.query(':TRIGger:LEVel:HIGH 1,CHANnel 1')
        self.scope.query(":TRIGger:MODE EDGE")
        self.scope.query(":TRIGger:EDGE:LEVel 1")
        self.scope.query(":TIMebase:SCALe 5e-8")

        #self.scope.single()
        # TODO: Make per-shot acquisition parameters and channels configurable here
        
        # Unlocking the front Buttons of the osci after buffered mode
        #self.scope.unlock()

        self.buffered_mode = True       # confirm that we buffered
        return {}
    
    def transition_to_manual(self, abort = False):
        """
                Transition to manual mode after buffered execution completion.
                    
                Returns:
                    bool: `True` if transition to manual is successful.
        """
        self.logger.debug('Transition_to_manual Keysight')
        rich_print(f"====== transition_to_manual Keysight: {os.path.basename(self.h5file)} ======", color=GREEN)

        if not self.buffered_mode:              # In case we didnt take a shot
            return True
        self.buffered_mode = False              # reset the Flag to False 

        if abort:                               # If we aborted we dont want an acquisation
            self.acquired_data = None
            self.h5_file = None
            return True


        channels = self.scope.channels()
        data_dict = {}                          # Create Dict channel - data
        vals = {}
        wtype = [('t', 'float')]     

        for ch, enabled in channels.items():
            if enabled:
                data_dict[ch], t, vals[ch] = self.scope.waveform(
                    ch,
                    int16= False                                      
                )
                wtype.append((ch, 'float'))

        # Collect all data in a structured array
        data = np.empty(len(t), dtype=wtype)
        data['t'] = t
        for ch in vals:
            data[ch] = vals[ch]
        
        print(data)

        # Open the file after download so as not to hog the file lock
        # The Blacs worker of the Ni-CArd is responsible for creating the h5file for a shot ( From what i understood , can be wrong )
        with h5py.File(self.h5file, 'r+') as hdf_file:          # r+ : Read/write, file must exist 
            grp = hdf_file.create_group('/data/traces')
            print('Saving traces...')
            dset = grp.create_dataset(self.device_name, data=data)      
            dset.attrs.update(data_dict[ch])                        # This saves the preamble of the waveform
        print('Saving Done!')
        return True

    # ----------------------------------------- DONE 
    def abort_transition_to_buffered(self):
        """Special abort shot configuration code belongs here.
        """
        return self.transition_to_manual(True)
        
    def abort_buffered(self):
        """Special abort shot code belongs here.
        """
        return self.transition_to_manual(True)

    # ----------------------------------------- (Futur) Override for remote 
    def program_manual(self,front_panel_values):
        """Over-ride this method if remote programming is supported.
        
        Returns:
            :obj:`check_remote_values()`
        """

        return self.check_remote_values()

    def check_remote_values(self):
        # over-ride this method if remote value check is supported
        return {}