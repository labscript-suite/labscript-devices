Example Connection Tables
=========================

An example connection table for the experiment described in [1]_. This connection table makes extensive use of `user_devices`, by name of `naqslab_devices`.

.. code-block:: python

	from labscript import *
	from naqslab_devices.PulseBlasterESRPro300.labscript_device import PulseBlasterESRPro300
	from naqslab_devices.NovaTechDDS.labscript_device import NovaTech409B, NovaTech409B_AC
	from labscript_devices.NI_DAQmx.models.NI_USB_6343 import NI_USB_6343
	from naqslab_devices.SignalGenerator.Models import RS_SMA100B, SRS_SG386
	from naqslab_devices import ScopeChannel, StaticFreqAmp
	from naqslab_devices.KeysightXSeries.labscript_device import KeysightXScope
	#from labscript_devices.PylonCamera.labscript_devices import PylonCamera
	from naqslab_devices.KeysightDCSupply.labscript_device import KeysightDCSupply
	from naqslab_devices.SR865.labscript_device import SR865

	PulseBlasterESRPro300(name='pulseblaster_0', board_number=0, programming_scheme='pb_start/BRANCH')
	ClockLine(name='pulseblaster_0_clockline_fast', pseudoclock=pulseblaster_0.pseudoclock, connection='flag 0')
	ClockLine(name='pulseblaster_0_clockline_slow', pseudoclock=pulseblaster_0.pseudoclock, connection='flag 1')
		    
	NI_USB_6343(name='ni_6343', parent_device=pulseblaster_0_clockline_fast, 
	            clock_terminal='/ni_usb_6343/PFI0',
		    MAX_name='ni_usb_6343',
		    acquisition_rate = 243e3, # 500 kS/s max aggregate)
		    stop_order = -1) #as clocking device, ensure it transitions first

	NovaTech409B(name='novatech_static', com_port="com4", baud_rate = 115200, 
			phase_mode='aligned',ext_clk=True, clk_freq=100, clk_mult=5)
	NovaTech409B_AC(name='novatech', parent_device=pulseblaster_0_clockline_slow, 
			com_port="com3", update_mode='asynchronous', phase_mode='aligned', 
			baud_rate = 115200, ext_clk=True, clk_freq=100, clk_mult=5)

	# using NI-MAX alias instead of full VISA name
	RS_SMA100B(name='SMA100B', VISA_name='SMA100B')
	RS_SMA100B(name='SMA100B2', VISA_name='SMA100B-2')
	SRS_SG386(name='SG386', VISA_name='SG386-6181I', output='RF', mod_type='Sweep')

	# call the scope, use NI-MAX alias instead of full name
	KeysightXScope(name='Scope',VISA_name='DSOX3024T',
		trigger_device=pulseblaster_0.direct_outputs,trigger_connection='flag 3',
		num_AI=4,DI=False)
	ScopeChannel('Heterodyne',Scope,'Channel 1')
	#ScopeChannel('Absorption',Scope,'Channel 2')
	#ScopeChannel('Modulation',Scope,'Channel 4')

	# DC Supplies
	KeysightDCSupply(name='DCSupply',VISA_name='E3640A',
			 range='HIGH',volt_limits=(0,20),current_limits=(0,1))
	StaticAnalogOut('DCBias_Gnd',DCSupply,'channel 0')
	KeysightDCSupply(name='DCSupply2',VISA_name='E3644A',
			range='HIGH',volt_limits=(0,20),current_limits=(0,1))
	StaticAnalogOut('DCBias_Sig',DCSupply2,'channel 0')

	# Lock-In Amplifier
	SR865(name='LockIn',VISA_name='SR865')

	# Define Cameras
	# note that Basler cameras can overlap frames if 
	# second exposure does not end before frame transfer of first finishes

	'''	    
	PylonCamera('CCD_2',parent_device=pulseblaster_0.direct_outputs,connection='flag 6',
		    serial_number=21646179,
		    mock=False,
		    camera_attributes={'ExposureTime':9000,
				       'ExposureMode':'Timed',
				       'Gain':0.0,
				       'ExposureAuto':'Off',
				       'GainAuto':'Off',
				       'PixelFormat':'Mono12',
				       'Gamma':1.0,
				       'BlackLevel':0,
				       'TriggerSource':'Line1',
				       'ShutterMode':'Global',
				       'TriggerMode':'On'},
		    manual_mode_camera_attributes={'TriggerSource':'Software',
						   'TriggerMode':'Off'})
	'''
	# Define the Wait Monitor for the AC-Line Triggering
	# note that connections used here cannot be used elsewhere
	# 'connection' needs to be physically connected to 'acquisition_connection'
	# for M-Series DAQs, ctr0 gate is on PFI9
	WaitMonitor(name='wait_monitor', parent_device=ni_6343, 
		    connection='port0/line0', acquisition_device=ni_6343, 
		    acquisition_connection='ctr0', timeout_device=ni_6343, 
		    timeout_connection='PFI1')

	DigitalOut( 'AC_trigger_arm', pulseblaster_0.direct_outputs, 'flag 2')

	# define the PB digital outputs
	DigitalOut( 'probe_AOM_enable', pulseblaster_0.direct_outputs, 'flag 4')
	DigitalOut( 'LO_AOM_enable', pulseblaster_0.direct_outputs, 'flag 5')

	# short pulse control channels
	DigitalOut(  'bit21', pulseblaster_0.direct_outputs, 'flag 21')
	DigitalOut(  'bit22', pulseblaster_0.direct_outputs, 'flag 22')
	DigitalOut(  'bit23', pulseblaster_0.direct_outputs, 'flag 23')

	AnalogOut( 'ProbeAmpLock', ni_6343, 'ao0')
	AnalogOut( 'LOAmpLock', ni_6343, 'ao1')
	AnalogOut( 'blueSweep', ni_6343, 'ao2')
	AnalogOut( 'MW_Phase', ni_6343, 'ao3')

	AnalogIn( 'Homodyne', ni_6343, 'ai0')
	AnalogIn( 'AI1', ni_6343, 'ai1')
	AnalogIn( 'LockInX', ni_6343, 'ai2')
	AnalogIn( 'LockInY', ni_6343, 'ai3')

	# this dummy line necessary to balance the digital out for the wait monitor
	DigitalOut( 'P0_1', ni_6343, 'port0/line1')

	StaticDDS( 'Probe_EOM', novatech_static, 'channel 0')
	StaticDDS( 'Probe_AOM', novatech_static, 'channel 1')
	StaticDDS( 'LO_AOM', novatech_static, 'channel 2')
	StaticDDS( 'LO', novatech_static, 'channel 3')

	DDS( 'Probe_BN', novatech, 'channel 0')
	DDS( 'dds1', novatech, 'channel 1')
	StaticDDS( 'SAS_Mod', novatech, 'channel 2')
	StaticDDS( 'SAS_LO', novatech, 'channel 3')

	StaticFreqAmp( 'uWaves', SMA100B, 'channel 0', freq_limits=(8e-6,20), amp_limits=(-145,35))
	StaticFreqAmp( 'uWavesLO', SMA100B2, 'channel 0', freq_limits=(8e-6,20), amp_limits=(-145,35))
	StaticFreqAmp( 'blueEOM', SG386, 'channel 0', freq_limits=(1,6.075e3), amp_limits=(-110,16.5))

	start()

	stop(1)

References
~~~~~~~~~~

.. [1] D. H. Meyer, Z. A. Castillo, K. C. Cox, and P. D. Kunz, J. Phys B, **53** 034001 (2020)
		https://iopscience.iop.org/article/10.1088/1361-6455/ab6051