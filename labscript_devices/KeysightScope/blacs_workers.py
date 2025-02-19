import numpy as np
import os
import labscript_utils.h5_lock
import h5py
from zprocess import rich_print

from blacs.tab_base_classes import Worker
import labscript_utils.properties
import matplotlib.pyplot as plt
from matplotlib import pyplot as plt
from labscript_devices.KeysightScope.connection_manager import * 

BLUE = '#66D9EF'
PURPLE = '#AE81FF'
GREEN = '#A6E22E'
GREY = '#75715E' 

class KeysightScopeWorker(Worker):
    """
    Defines the software control interface to the hardware. 
    The BLACS_tab spawns a process that uses this class to send and receive commands with the hardware.
    """
    def init(self):

        global KeysightScope
        from .KeysightScope import KeysightScope
        self.scope = KeysightScope()

        # Buffered/ Manuel relevant flags
        self.buffered_mode = False
        self.acquired_data = None
        self.h5file = None
           

    def transition_to_buffered( self, device_name, h5file, front_panel_values, refresh):
        rich_print(f"====== transition to Buffered: ======", color=BLUE)    # os.path.basename(self.h5file)
        self.scope.single()

        self.h5file = h5file                                                    
        self.device_name = device_name

        # These two are not used yet 
        self.initial_values =  front_panel_values # Store the initial values in case we have to abort and restore them:
        self.final_values = {}  # Store the final values to for use during transition_to_static:


        with h5py.File(h5file, 'r') as hdf5file:
            # Dictionary of properties
            self.scope_params = labscript_utils.properties.get(hdf5file, device_name, 'device_properties')

        self.buffered_mode = True       # confirm that we buffered
        return {}
    
    def transition_to_manual(self, abort = False):
        """
                Transition to manual mode after buffered execution completion.
                    
                Returns:
                    bool: `True` if transition to manual is successful.
        """
        rich_print(f"====== transition to manual: ======", color=GREEN)

        if not self.buffered_mode:              # In case we didnt take a shot
            return True
        self.buffered_mode = False              # reset the Flag to False 

        if abort:                               # If we aborted we dont want an acquisation
            self.acquired_data = None
            self.h5file = None
            return True

        channels = self.scope.channels()
        data_dict = {}                          # Create Dict channel - data
        vals = {}
        wtype = [('t', 'float')]     
        for ch, enabled in channels.items():
            if enabled:
                data_dict[ch], t, vals[ch] = self.scope.waveform(ch)
                wtype.append((ch, 'float'))

        # Collect all data in a structured array
        data = np.empty(len(t), dtype=wtype)
        data['t'] = t   
        for ch in vals:
            data[ch] = vals[ch] 
        #     plt.xlabel('Time in s')
        #     plt.ylabel('Voltage(2V)')
        #     plt.plot(data['t'],vals[ch])
        # plt.show()

     
        # The Blacs worker of the Ni-CArd is responsible for creating the h5file for a shot ( From what i understood , can be wrong )
        with h5py.File(self.h5file, 'r+') as hdf_file:          # r+ : Read/write, file must exist 
            grp = hdf_file.create_group('/data/traces')
            dset = grp.create_dataset(f"{self.device_name } {self.scope.description}" , data=data)    
            dset.attrs.update(self.scope.osci_capabilities) 
            #dset.attrs.update(data_dict[ch])                    # This saves the preamble of the waveform
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