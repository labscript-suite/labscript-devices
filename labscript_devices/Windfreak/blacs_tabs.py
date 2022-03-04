#####################################################################
#                                                                   #
# /labscript_devices/Windfreak/blacs_tabs.py                        #
#                                                                   #
# Copyright 2022, Monash University and contributors                #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

from blacs.device_base_class import DeviceTab


class WindfreakSynthTab(DeviceTab):

    def __init__(self, *args, **kwargs):
        if not hasattr(self,'device_worker_class'):
            self.device_worker_class = 'labscript_devices.Windfreak.blacs_workers.WindfreakSynthWorker'
        DeviceTab.__init__(self, *args, **kwargs)

    def initialise_GUI(self):

        print(self.settings)
        conn_obj = self.settings['connection_table'].find_by_name(self.device_name).properties

        self.allowed_chans = conn_obj.get('allowed_chans',None)

        # finish populating these from device properties
        chan_prop = {'freq':{},'amp':{},'phase':{},'gate':{}}
        freq_limits = conn_obj.get('freq_limits',None)
        chan_prop['freq']['min'] = freq_limits[0]
        chan_prop['freq']['max'] = freq_limits[1]
        chan_prop['freq']['decimals'] = conn_obj.get('freq_res',None)
        chan_prop['freq']['base_unit'] = 'Hz'
        chan_prop['freq']['step'] = 100
        amp_limits = conn_obj.get('amp_limits',None)
        chan_prop['amp']['min'] = amp_limits[0]
        chan_prop['amp']['max'] = amp_limits[1]
        chan_prop['amp']['decimals'] = conn_obj.get('amp_res',None)
        chan_prop['amp']['base_unit'] = 'dBm'
        chan_prop['amp']['step'] = 1
        phase_limits = conn_obj.get('phase_limits',None)
        chan_prop['phase']['min'] = phase_limits[0]
        chan_prop['phase']['max'] = phase_limits[1]
        chan_prop['phase']['decimals'] = conn_obj.get('phase_res',None)
        chan_prop['phase']['base_unit'] = 'deg'
        chan_prop['phase']['step'] = 1

        dds_prop = {}
        for chan in self.allowed_chans:
            dds_prop[f'channel {chan:d}'] = chan_prop

        self.create_dds_outputs(dds_prop)
        dds_widgets,ao_widgets,do_widgets = self.auto_create_widgets()
        self.auto_place_widgets(('Synth Outputs',dds_widgets))

        DeviceTab.initialise_GUI(self)

        # set capabilities
        self.supports_remote_value_check(True)
        self.supports_smart_programming(True)
        #self.statemachine_timeout_add(5000,self.status_monitor)

    def initialise_workers(self):

        conn_obj = self.settings['connection_table'].find_by_name(self.device_name).properties
        self.com_port = conn_obj.get('com_port',None)
        self.trigger_mode = conn_obj.get('trigger_mode','disabled')

        self.create_worker('main_worker',self.device_worker_class,{'com_port':self.com_port,
                                                                   'allowed_chans':self.allowed_chans,
                                                                   'trigger_mode':self.trigger_mode})

        self.primary_worker = 'main_worker'
