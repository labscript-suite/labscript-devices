#####################################################################
#                                                                   #
# /naqslab_devices/NovaTechDDS/blacs_tab.py                         #
#                                                                   #
# Copyright 2018, David Meyer                                       #
#                                                                   #
# This file is part of naqslab_devices,                             #
# and is licensed under the                                         #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
# Source borrows heavily from labscript_devices/NovaTechDDS9m       #
#                                                                   #
#####################################################################
from blacs.device_base_class import DeviceTab

class NovaTech409B_ACTab(DeviceTab):

    def __init__(self,*args,**kwargs):
        if not hasattr(self,'device_worker_class'):
            self.device_worker_class = "naqslab_devices.NovaTechDDS.blacs_worker.NovaTech409B_ACWorker"
        DeviceTab.__init__(self,*args,**kwargs)

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
            dds_prop['channel %d' % i] = {}
            for subchnl in ['freq', 'amp', 'phase']:
                dds_prop['channel %d' % i][subchnl] = {'base_unit':self.base_units[subchnl],
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
        conn_properties = connection_object.properties
        
        # Store the COM port to be used
        blacs_connection =  str(connection_object.BLACS_connection)
        if ',' in blacs_connection:
            self.com_port, baud_rate = blacs_connection.split(',')
            self.baud_rate = int(baud_rate)
        else:
            self.com_port = blacs_connection
            self.baud_rate = 19200
        
        self.update_mode = conn_properties.get('update_mode', 'synchronous')
        self.phase_mode = conn_properties.get('phase_mode', 'default')
        # clocking properties
        self.R_option = conn_properties.get('R_option',False)
        self.ext_clk = conn_properties.get('ext_clk',False)
        self.kp = conn_properties.get('kp',None)
        self.clk_scale = conn_properties.get('clk_scale',1)
        
        # Create and set the primary worker
        worker_init_kwargs = {'com_port': self.com_port,
                              'baud_rate': self.baud_rate,
                              'update_mode': self.update_mode,
                              'phase_mode': self.phase_mode,
                              'R_option': self.R_option,
                              'ext_clk': self.ext_clk,
                              'kp': self.kp,
                              'clk_scale': self.clk_scale}
        self.create_worker("main_worker",
                           self.device_worker_class,
                           worker_init_kwargs)
        self.primary_worker = "main_worker"

        # Set the capabilities of this device
        self.supports_remote_value_check(True)
        self.supports_smart_programming(True) 


class NovaTech409BTab(NovaTech409B_ACTab):
    
    def __init__(self,*args,**kwargs):
        self.device_worker_class = "naqslab_devices.NovaTechDDS.blacs_worker.NovaTech409BWorker"
        NovaTech409B_ACTab.__init__(self,*args,**kwargs)

class NovaTech440ATab(NovaTech409B_ACTab):
    
    def __init__(self,*args,**kwargs):
        if not hasattr(self,'device_worker_class'):
            self.device_worker_class = "naqslab_devices.NovaTechDDS.blacs_worker.NovaTech440AWorker"
        DeviceTab.__init__(self,*args,**kwargs)
        
    def initialise_GUI(self):        
        # Capabilities
        self.base_units =    {'freq':'Hz',               'phase':'Degrees'}
        self.base_min =      {'freq':200e3,              'phase':0}
        self.base_max =      {'freq':402.653183*10.0**6, 'phase':360}
        self.base_step =     {'freq':10**6,              'phase':1}
        self.base_decimals = {'freq':0,                  'phase':3} # TODO: find out what the phase precision is!
        self.num_DDS = 1
        
        # Create DDS Output objects
        dds_prop = {}
        for i in range(self.num_DDS): # only 1 DDS output
            dds_prop['channel %d' % i] = {}
            for subchnl in ['freq', 'phase']:
                dds_prop['channel %d' % i][subchnl] = {'base_unit':self.base_units[subchnl],
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
        conn_properties = connection_object.properties
        
        # Store the COM port to be used
        blacs_connection =  str(connection_object.BLACS_connection)
        if ',' in blacs_connection:
            self.com_port, baud_rate = blacs_connection.split(',')
            self.baud_rate = int(baud_rate)
        else:
            self.com_port = blacs_connection
            self.baud_rate = 19200
            
        self.ext_clk = conn_properties.get('ext_clk',False)
        self.clk_freq = conn_properties.get('clk_freq', None)
        self.clk_scale = conn_properties.get('clk_scale',1)
        
        # Create and set the primary worker
        self.create_worker("main_worker",self.device_worker_class,
                                {'com_port':self.com_port,
                                'baud_rate': self.baud_rate,
                                'ext_clk': self.ext_clk,
                                'clk_freq': self.clk_freq,
                                'clk_scale': self.clk_scale
                                })
        self.primary_worker = "main_worker"

        # Set the capabilities of this device
        self.supports_remote_value_check(True)
        self.supports_smart_programming(True)
