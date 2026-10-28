#####################################################################
#                                                                   #
# /labscript_devices/NovaTechDDS9M/blacs_tabs.py                    #
#                                                                   #
# Copyright 2013, Monash University                                 #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################
from blacs.device_base_class import DeviceTab


class NovatechDDS9MTab(DeviceTab):
    def initialise_GUI(self):        
        # Capabilities
        self.base_units =    {'freq':'Hz',          'amp':'Arb',   'phase':'Degrees'}
        self.base_min =      {'freq':0.0,           'amp':0,       'phase':0}
        self.base_max =      {'freq':170.0*10.0**6, 'amp':1,       'phase':360}
        self.base_step =     {'freq':10**6,         'amp':1/1023., 'phase':1}
        self.base_decimals = {'freq':1,             'amp':4,       'phase':3} # TODO: find out what the phase precision is!
        self.num_DDS = 4
        
        # Create DDS Output objects
        dds_prop = {}
        for i in range(self.num_DDS): # 4 is the number of DDS outputs on this device
            dds_prop['channel %d'%i] = {}
            for subchnl in ['freq', 'amp', 'phase']:
                dds_prop['channel %d'%i][subchnl] = {'base_unit':self.base_units[subchnl],
                                                     'min':self.base_min[subchnl],
                                                     'max':self.base_max[subchnl],
                                                     'step':self.base_step[subchnl],
                                                     'decimals':self.base_decimals[subchnl]
                                                    }
        # Create the output objects    
        self.create_dds_outputs(dds_prop)        
        # Create widgets for output objects
        dds_widgets,ao_widgets,do_widgets = self.auto_create_widgets()
        # and auto place the widgets in the UI
        self.auto_place_widgets(("DDS Outputs",dds_widgets))
        
        connection_object = self.settings['connection_table'].find_by_name(self.device_name)
        connection_table_properties = connection_object.properties
        
        self.phase_mode = connection_table_properties.get('phase_mode', 'continuous')

        self.com_port = connection_table_properties.get('com_port', None)
        self.baud_rate = connection_table_properties.get('baud_rate', None)
        self.default_baud_rate = connection_table_properties.get('default_baud_rate', None)
        self.update_mode = connection_table_properties.get('update_mode', 'synchronous')
        
        # Backward compat:
        blacs_connection =  str(connection_object.BLACS_connection)
        if ',' in blacs_connection:
            com_port, baud_rate = blacs_connection.split(',')
            if self.com_port is None:
                self.com_port = com_port
            if self.baud_rate is None:
                self.baud_rate = int(baud_rate)
        else:
            self.com_port = blacs_connection
            self.baud_rate = 115200
        


        # Create and set the primary worker
        self.create_worker("main_worker","labscript_devices.NovaTechDDS9M.blacs_workers.NovatechDDS9mWorker",{'com_port':self.com_port,
                                                              'baud_rate': self.baud_rate,
                                                              'default_baud_rate': self.default_baud_rate,
                                                              'update_mode': self.update_mode,
                                                              'phase_mode': self.phase_mode})
        self.primary_worker = "main_worker"

        # Set the capabilities of this device
        self.supports_remote_value_check(True)
        self.supports_smart_programming(True) 
