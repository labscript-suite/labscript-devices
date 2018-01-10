# A labscript device class for data acquisition boards made by Alazar Technologies Inc (ATS)
# Hacked up from NIBoard.py by LDT 2017-01-26
#
# Copyright (c) Monash University 2017

if __name__ != "__main__":
    import numpy as np
    from labscript_devices import labscript_device
    from labscript import Device, AnalogIn, bitfield, config, LabscriptError, set_passed_properties
    import labscript_utils.h5_lock, h5py
    import labscript_utils.properties
    import labscript_utils.shared_drive as shared_drive
    import atsapi as ats

    class AlazarTechBoard(Device):
        allowed_children = [AnalogIn]
        description = 'Generic_Alazar_Technologies_capture_board'

    # Many properties not supported. Examples include:
    # AlazarSetExternalClockLevel, SetDataFormat
    # Anything to do with onboard memory
    # Anything "for scanning"
    
        @set_passed_properties(property_names = {
            "device_properties":["ats_system_id", "ats_board_id",
                             "requested_acquisition_rate",
                             "clock_source_id", "sample_rate_id_or_value", "clock_edge_id", "decimation",
                             "trig_operation",
                             "trig_engine_id1", "trig_source_id1", "trig_slope_id1",  "trig_level_id1",
                             "trig_engine_id2", "trig_source_id2", "trig_slope_id2", "trig_level_id2",
                             "exttrig_coupling_id", "exttrig_range_id",
                             "trig_delay_samples", "trig_timeout_10usecs", "input_range"]
        })
    
        def __init__(self, name, server,
                     ats_system_id=1, ats_board_id=1,
                     requested_acquisition_rate=0, # No default for this, must be calculated and set!
                     clock_source_id         = ats.INTERNAL_CLOCK,
                     sample_rate_id_or_value = ats.SAMPLE_RATE_180MSPS,
                     clock_edge_id           = ats.CLOCK_EDGE_RISING,
                     decimation              = 0, 
                     trig_operation          = ats.TRIG_ENGINE_OP_J,
                     trig_engine_id1         = ats.TRIG_ENGINE_J,
                     trig_source_id1         = ats.TRIG_EXTERNAL,
                     trig_slope_id1          = ats.TRIGGER_SLOPE_POSITIVE,
                     trig_level_id1          = 128, # 0 mV
                     trig_engine_id2         = ats.TRIG_ENGINE_K,
                     trig_source_id2         = ats.TRIG_DISABLE,
                     trig_slope_id2          = ats.TRIGGER_SLOPE_POSITIVE,
                     trig_level_id2          = 128, # 0 mV
                     exttrig_coupling_id     = ats.DC_COUPLING,
                     exttrig_range_id        = ats.ETR_5V,
                     trig_delay_samples      =0,
                     trig_timeout_10usecs    =0,
                     input_range             =4000):
            Device.__init__(self, name, None, None)
            # self.acquisition_rate = acquisition_rate
            # self.clock_terminal = clock_terminal
            # self.clock_source_id         = clock_source_id         
            # self.sample_rate_id_or_value = sample_rate_id_or_value 
            # self.clock_edge_id           = clock_edge_id           
            # self.decimation              = decimation              
            # self.trig_operation          = trig_operation          
            # self.trig_engine_id1         = trig_engine_id1         
            # self.trig_source_id1         = trig_source_id1         
            # self.trig_slope_id1          = trig_slope_id1          
            # self.trig_level_id1          = trig_level_id1          
            # self.trig_engine_id2         = trig_engine_id2         
            # self.trig_source_id2         = trig_source_id2         
            # self.trig_slope_id2          = trig_slope_id2          
            # self.trig_level_id2          = trig_level_id2          
            # self.exttrig_coupling_id     = exttrig_coupling_id     
            # self.exttrig_range_id        = exttrig_range_id        
            # self.trig_delay_samples      = trig_delay_samples      
            # self.trig_timeout_10usecs    = trig_timeout_10usecs    
            self.BLACS_connection        = server

        def add_device(self, output):
            # TODO: check there are no duplicates, check that connection
            # string is formatted correctly.
            Device.add_device(self, output)

        # Has no childern for now so hopefully does nothing
        def generate_code(self, hdf5_file):
            Device.generate_code(self, hdf5_file)
            inputs = {}
            for device in self.child_devices:
                if isinstance(device, AnalogIn):
                    inputs[device.connection] = device
                else:
                    raise Exception('Got unexpected device.')
            input_connections = inputs.keys()
            input_connections.sort()
            input_attrs = []
            acquisitions = []
            for connection in input_connections:
                input_attrs.append(self.name+'/'+connection)
                for acq in inputs[connection].acquisitions:
                    acquisitions.append((connection,acq['label'],acq['start_time'],acq['end_time'],acq['wait_label'],acq['scale_factor'],acq['units']))
            acquisitions_table_dtypes = [('connection','a256'), ('label','a256'), ('start',float),
                                         ('stop',float), ('wait label','a256'),('scale factor',float), ('units','a256')]
            acquisition_table= np.empty(len(acquisitions), dtype=acquisitions_table_dtypes)
            for i, acq in enumerate(acquisitions):
                acquisition_table[i] = acq
                grp = self.init_device_group(hdf5_file)
            if len(acquisition_table): # Table must be non empty
                grp.create_dataset('ACQUISITIONS',compression=config.compression,data=acquisition_table)
                self.set_property('analog_in_channels', ', '.join(input_attrs), location='device_properties')

    from labscript_devices import BLACS_tab, BLACS_worker
    from blacs.tab_base_classes import Worker, define_state
    from blacs.tab_base_classes import MODE_MANUAL, MODE_TRANSITION_TO_BUFFERED, MODE_TRANSITION_TO_MANUAL, MODE_BUFFERED 
    from blacs.device_base_class import DeviceTab
    import os
    from qtutils import UiLoader
    
    # A BLACS tab for a purely remote device which does not need configuration of parameters in BLACS
    @BLACS_tab
    class RemoteControllerTab(DeviceTab):
        def initialise_GUI(self):
            layout = self.get_tab_layout()
            ui_filepath = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'alazar.ui')
            self.ui = UiLoader().load(ui_filepath)
            layout.addWidget(self.ui)
            self.server = str(self.settings['connection_table'].find_by_name(self.device_name).BLACS_connection)
            self.host, self.port = self.server.split(':')
            self.ui.port_label.setText(str(self.port)) 
            self.ui.is_responding.setVisible(False)
            self.ui.is_not_responding.setVisible(False)
            self.ui.host_lineEdit.returnPressed.connect(self.update_settings_and_check_connectivity)
            self.ui.check_connectivity_pushButton.clicked.connect(self.update_settings_and_check_connectivity)

        def get_save_data(self):
            return {'host': str(self.ui.host_lineEdit.text())}

        def restore_save_data(self, save_data):
            print 'restore save data running'
            if save_data:
                host = save_data['host']
                self.ui.host_lineEdit.setText(host)
            else:
                self.logger.warning('No previous front panel state to restore')
            if self.primary_worker:
                self.update_settings_and_check_connectivity()

        def initialise_workers(self):
            # Create and set the primary worker
            self.create_worker("main_worker",RemoteControllerWorker,{'server':self.server})
            self.primary_worker = "main_worker"
            self.update_settings_and_check_connectivity()

        @define_state(MODE_MANUAL, queue_state_indefinitely=True, delete_stale_states=True)
        def update_settings_and_check_connectivity(self, *args):
            self.ui.saying_hello.setVisible(True)
            self.ui.is_responding.setVisible(False)
            self.ui.is_not_responding.setVisible(False)
            kwargs = self.get_save_data()
            responding = yield(self.queue_work(self.primary_worker, 'update_settings_and_check_connectivity', **kwargs))
            self.update_responding_indicator(responding)

        def update_responding_indicator(self, responding):
            self.ui.saying_hello.setVisible(False)
            if responding:
                self.ui.is_responding.setVisible(True)
                self.ui.is_not_responding.setVisible(False)
            else:
                self.ui.is_responding.setVisible(False)
                self.ui.is_not_responding.setVisible(True)

    @BLACS_worker    
    class RemoteControllerWorker(Worker):
        def init(self):
            global h5py; import labscript_utils.h5_lock, h5py
            global zprocess; import zprocess
            self.host, self.port = self.server.split(':')
            self.update_settings_and_check_connectivity(self.host)

        def send_data(self, data):
            return zprocess.zmq_get_string(self.port, self.host, data=data, timeout=10)

        # This is necessary for dynamic changing of the host target,
        # as well as 'ping'.
        def update_settings_and_check_connectivity(self, host):
            self.host = host
            if not self.host:
                return False
            response = self.send_data('hello')
            if response == 'hello':
                return True
            raise Exception('invalid response from server: ' + str(response))

        def transition_to_buffered(self,device_name,h5file,initial_values,fresh):
            self.h5file = h5file # We'll need this in transition_to_manual
            with h5py.File(h5file) as hdf5_file:
                group = hdf5_file['/devices/'+device_name]
                #self.board_attributes = group.attrs.copy()
            self.qualh5file = shared_drive.path_to_agnostic(h5file)
            response = self.send_data(self.qualh5file)
            if response != 'ok':
                raise Exception('Failed to transition to buffered. Message from server was: %s'%response)
            return {} # ? Check this

        def program_manual(self,values):
            #for now, there is no manual mode
            return values

        def transition_to_manual(self):
            # Shaun uses this in preference to Camera.py's "done". I think this is better.
            response = self.send_data("transition_to_manual")
            if response != 'ok':
                raise Exception('Failed to transition to manual.  Message from server was: %s'%response)
            return True

        def abort(self):
            response = self.send_data("transition_to_manual")
            if response != 'ok':
                raise Exception('Failed to abort.  Message from server was: %s'%response)
            return True

        def abort_buffered(self):
            return self.abort()

        def abort_transition_to_buffered(self):
            return self.abort()


        
#####################################################
#
# The server code
#
#####################################################

if __name__ == "__main__":   
    from zprocess import zmq_get, ZMQServer
    # Set up the process which will run during the experiment
    
    class RemoteServer(ZMQServer):
        def __init__(self, *args, **kwargs):
            ZMQServer.__init__(self, *args, **kwargs)
            self.buffered = False
#            self.initialised = False

#        def initialise(self):
#            print "Initialising"
#            self.initialised = True
#            return 'ok'

        def handler(self, message):
            print message
            message_parts = message.split(' ')
            cmd = message_parts[0]
            
#            if not self.initialised:
#                if cmd != 'initialise':
#                    return 'Server not yet initialised. Please send the initialise command.'

#           if cmd == 'initialise':
#                self.buffered = False
#                return self.initialise()              
            if cmd == 'transition_to_buffered':
                self.abort.clear()
                focus = message_parts[1]
                # first, check that the stages are in the MOT position.
                lens_position = check_stage_position(lens_stage)
                mirror_position = check_stage_position(mirror_stage)

                if lens_position != lens_mot_position or mirror_position != mirror_mot_position:
                    move_to_MOT()
                # now tell parent that we're ready to go
                ret_message = 'ok'            
                self.experiment = threading.Thread(target = self.run_experiment, args = (focus,))
                self.experiment.daemon = True
                self.experiment.start()
                self.buffered = True

            elif cmd == 'transition_to_manual':
                self.abort.set()
                self.experiment.join()
                lens_position = check_stage_position(lens_stage)
                mirror_position = check_stage_position(mirror_stage)
                if lens_position != lens_mot_position or mirror_position != mirror_mot_position:
                    move_to_MOT()
                self.buffered = False
                ret_message = 'ok'

            else:
                ret_message = 'Unknown command %s'%cmd
                
            return ret_message

    experiment_server = ExperimentServer(42522)
    while True:
        time.sleep(1)
        
