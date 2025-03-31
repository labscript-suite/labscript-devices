import numpy as np
import os
import labscript_utils.h5_lock
import h5py
from zprocess import rich_print
from blacs.tab_base_classes import Worker
from  labscript_utils import properties

from matplotlib import pyplot as plt
from labscript_devices.KeysightScope.connection_manager import BLUE,GREEN,PURPLE


class KeysightScopeWorker(Worker):
    """
    Defines the software control interface to the hardware. 
    The BLACS_tab spawns a process that uses this class to communicate with the hardware.
    """
    def init(self):
        # ----------------------------------------- Initialize osci
        global KeysightScope
        from .KeysightScope import KeysightScope
        self.scope = KeysightScope(
            address= self.address,
            verbose = False)

        # ----------------------------------------- Configurations attributes
        self.configuration_register = {}           # Docu : KeysightScope.get_saving_register()
        self.activated_configuration = 0

        # ----------------------------------------- Buffered/Manuel flags
        self.buffered_mode = False
           
    def transition_to_buffered( self, device_name, h5file , front_panel_values, refresh): 
        rich_print(f"====== Begin transition to Buffered: ======", color=BLUE)    
        
        self.h5file = h5file                                                    
        self.device_name = device_name

        with h5py.File(self.h5file, 'r+') as f: 
            
            # ----------------------------------------- Get device properties
            self.activated_configuration = properties.get(f, device_name, 'device_properties')["configuration_number"]
            self.triggered = properties.get(f, device_name, 'device_properties')["triggered"]
            self.timeout = properties.get(f, device_name, 'device_properties')["timeout"]

            self.current_configuration =  self.configuration_register[int(self.activated_configuration)]
  
            # ----------------------------------------- Error handling
            # --- Finish if no trigger
            if not self.triggered:
                return {}
            
            # --- Trigger source must be external
            trigger_source =  self.current_configuration["trigger_source"]                      
            if not (trigger_source == "EXT" or trigger_source == "EXTernal"):
                raise KeyError("Trigger source must be an external trigger source (EXT), not channel")
            
            # ----------------------------------------- Update configuration dictionary
            self.current_configuration["triggered"] = self.triggered
            self.current_configuration["timeout"] = self.timeout


        # ----------------------------------------- Setting the oscilloscope
        self.scope.recall_start_setup(self.activated_configuration)
        self.scope.dev.timeout = 1e3 *float(self.timeout)      # Set Timeout
        self.scope.single()

        self.buffered_mode = True       # confirm that we buffered
        self.scope.lock()               # Lock The oscilloscope
        rich_print(f"====== End transition to Buffered: ======", color=BLUE)  
        return {}
    
    def transition_to_manual(self, abort = False):
        rich_print(f"====== Begin transition to manual: ======", color=GREEN)
        self.scope.unlock()                                 # Unlocks The oscilloscope

        if (not self.buffered_mode) or abort :              # In case we didn't take a shot
            return True
        self.buffered_mode = False                          # reset the Flag to False 

        channels = self.scope.channels()                    # Get the dispayed channels
        data_dict = {}                                      # Create Dict channel - data
        vals = {}
        wtype = [('t', 'float')]     
        for ch, enabled in channels.items():
            if enabled:
                data_dict[ch], t, vals[ch] = self.scope.waveform(waveform_format= "BYTE", channel= ch )
                wtype.append((ch, 'float'))

        data = np.empty(len(t), dtype=wtype)                # Collect all data in a structured array
        data['t'] = t   
        for ch in vals:
            data[ch] = vals[ch] 
        #     plt.xlabel('Time')
        #     plt.ylabel('Voltage')
        #     plt.plot(data['t'],vals[ch])
        # plt.show()

        with h5py.File(self.h5file, 'r+') as hdf_file:          # r+ : Read/write, file must already exist 
            grp = hdf_file.create_group('/data/traces')
            dset = grp.create_dataset(self.device_name , data=data)       
            dset.attrs.update(data_dict[ch])                   # This saves the preamble of the waveform
            dset.attrs.update(self.current_configuration)
        
        self.scope.single()
        rich_print(f"====== End transition to manual: ======", color=GREEN)
        return True

    # ----------------------------------------- Aborting
    def abort_transition_to_buffered(self):
        """Special abort shot configuration code belongs here.
        """
        return self.transition_to_manual(True)
        
    def abort_buffered(self):
        """Special abort shot code belongs here.
        """
        return self.transition_to_manual(True)

    # ----------------------------------------- Override for remote 
    def program_manual(self,front_panel_values):
        """Over-ride this method if remote programming is supported.
        
        Returns:
            :obj:`check_remote_values()`
        """
        return self.check_remote_values()

    def check_remote_values(self):
        # over-ride this method if remote value check is supported
        return {}
    
    # ------------------------------------------ Blacs Tabs functions
    def shutdown(self):
        rich_print(f"====== transition to manual: ======", color= PURPLE)
        return self.scope.close()
    
    # ------------------------------------------ New
    def init_osci(self):
        self.configuration_register = self.scope.get_saving_register()
        self.scope.recall_start_setup()
        return self.configuration_register
    
    def activate_radio_button(self,value):
        self.scope.recall_start_setup(location= value)


    def load_current_config(self,value):
        self.scope.save_start_setup(value)
        new_configuration = self.scope.get_settings_dict(value)
        self._refresh_configuration_register(value , new_configuration)
        return new_configuration
    
    def default_config(self, value):
        self.scope.reset_device()
        self.scope.save_start_setup(value)
        new_configuration = self.scope.get_settings_dict(value)
        self._refresh_configuration_register(value , new_configuration)
        return new_configuration
    
    def _refresh_configuration_register(self , slot , new_configuration):
        self.configuration_register[slot] = new_configuration

    