#####################################################################
#                                                                   #
# /labscript_devices/AD9959DDSSweeper/blacs_tabs.py                 #
#                                                                   #
# Copyright 2025, Carter Turnbaugh                                  #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################

from blacs.device_base_class import DeviceTab

class AD9959DDSSweeperTab(DeviceTab):
	def initialise_GUI(self):
		# Capabilities
		self.base_units =    {'freq':'Hz',          'amp':'Arb',   'phase':'Degrees'}
		self.base_min =      {'freq':0.0,           'amp':0,       'phase':0}
		self.base_max =      {'freq':250.0*10.0**6, 'amp':1,       'phase':360}
		self.base_step =     {'freq':10**6,         'amp':1/1023., 'phase':1}
		self.base_decimals = {'freq':1,             'amp':4,       'phase':3}
		self.num_DDS = 4

		dds_prop = {}
		for i in range(self.num_DDS):
			dds_prop['channel %d' % i] = {}
			for subchnl in ['freq', 'amp', 'phase']:
				dds_prop['channel %d' % i][subchnl] = {'base_unit':self.base_units[subchnl],
													   'min':self.base_min[subchnl],
													   'max':self.base_max[subchnl],
													   'step':self.base_step[subchnl],
													   'decimals':self.base_decimals[subchnl]
													   }

		self.create_dds_outputs(dds_prop)
		dds_widgets, _, _ = self.auto_create_widgets()
		self.auto_place_widgets(('DDS Outputs', dds_widgets))

		device = self.settings['connection_table'].find_by_name(self.device_name)

		self.com_port = device.properties['com_port']

		self.supports_remote_value_check(False)
		self.supports_smart_programming(True)

	def initialise_workers(self):
		self.create_worker(
			"main_worker",
			"labscript_devices.AD9959DDSSweeper.blacs_workers.AD9959DDSSweeperWorker",
			{
				'com_port': self.com_port,
			},
		)
		self.primary_worker = "main_worker"
