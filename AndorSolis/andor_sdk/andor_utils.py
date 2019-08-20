import numpy as np 
import time

from .andor_solis import *
from .andor_capabilities import *

from zprocess import rich_print

s, ms, us, ns = 1.0, 1e-3, 1e-6, 1e-9

class AndorCam(object):
    
    def __init__(self, name='andornymous'):

        """ Methods of this class pack the sdk functions
        and define more convenient functions to carry out
        an acquisition """

        # WhoamI?
        self.name = name

        # Do I want to know everything about you?
        self.chatty = True

        # State
        self.cooling = False
        self.preamp = False
        self.emccd = False
        self.armed = False
        self.initialize_camera()
        
        self.default_acquisition_attrs = {
            'acquisition': 'single',
            'emccd': False,
            'emccd_gain': 120,
            'preamp': False,
            'preamp_gain': 1.0,
            'exposure_time': 20 * ms,
            'shutter_output': 'low',
            'int_shutter_mode': 'auto',
            'ext_shutter_mode': 'auto',
            'shutter_t_open': 100,
            'shutter_t_close': 100,
            'readout': 'full_image',
            'crop': False,
            'trigger': 'internal',
            'trigger_edge': 'rising',
            'number_accumulations': 1,
            'accumulation_period': 3 * ms,
            'number_kinetics': 1,
            'kinetics_period': 30 * ms,
            'xbin': 1,
            'ybin': 1,
            'center_row': None,
            'height': 1024,
            'width': 1024,
            'left_start': 1,
            'bottom_start': 1,
            'v_offset': 0,
            'acquisition_timeout': 5 / ms,
        }

    def initialize_camera(self):
        """ Calls the initialization function and
        pulls several properties from the hardware side such 
        as information and capabilities, which are useful for
        future acquisition settings """
        rich_print('Connecting to camera...', color='yellow')
        Initialize()
        self.serial_number = GetCameraSerialNumber()
    
        # Pull model and other capabilities struct
        self.check_capabilities()

        # Pull hardware attributes
        self.head_name = GetHeadModel()
        self.x_size, self.y_size = GetDetector()
        self.x_pixel_size, self.y_pixel_size = GetPixelSize()
        self.hardware_version = GetHardwareVersion()

        # Pull software attributes
        self.software_version = GetSoftwareVersion()

        # Pull important capability ranges
        self.temperature_range = GetTemperatureRange()
        self.emccd_gain_range = GetEMGainRange()
        self.number_of_preamp_gains = GetNumberPreAmpGains()
        self.preamp_gain_range = (
            GetPreAmpGain(0),
            GetPreAmpGain(self.number_of_preamp_gains - 1),
        )

    def check_capabilities(self):
        """ Do checks based on the _AC dict """
        # Pull the hardware noted capabilities
        self.andor_capabilities = GetCapabilities()

        self.model = camera_type.get_type(self.andor_capabilities.ulCameraType)

        self.acq_caps = acq_mode.check(self.andor_capabilities.ulAcqModes)
        self.read_caps = read_mode.check(self.andor_capabilities.ulReadModes)
        self.trig_capability = trigger_mode.check(
            self.andor_capabilities.ulTriggerModes
        )
        self.pixmode = pixel_mode.check(self.andor_capabilities.ulPixelMode)
        self.setfuncs = set_functions.check(self.andor_capabilities.ulSetFunctions)
        self.getfuncs = get_functions.check(self.andor_capabilities.ulGetFunctions)
        self.features = features.check(self.andor_capabilities.ulFeatures)
        self.emgain_capability = em_gain.check(
            self.andor_capabilities.ulEMGainCapability
        )

        if self.chatty:
            rich_print(f"Camera Capabilities", color='cornflowerblue')
            rich_print(f"   acq_caps: {self.acq_caps}", color='lightsteelblue')
            rich_print(f"   read_caps: {self.read_caps}", color='lightsteelblue')
            rich_print(f"   trig_caps: {self.trig_capability}", color='lightsteelblue')
            rich_print(f"   pixmode: {self.pixmode}", color='lightsteelblue')
        
            rich_print(f"   model: {self.model}", color='goldenrod')
            rich_print(f"   settable funcs: {self.setfuncs}", color='firebrick')
            rich_print(f"   get funcs: {self.getfuncs}", color='firebrick')
            rich_print(f"   features: {self.features}", color='lightsteelblue')
            rich_print(f"   emgain_caps: {self.emgain_caps}", color='lightsteelblue')

    def enable_cooldown(self, temperature_setpoint=20):
        """ Calls all the functions relative to temperature control
        and stabilization. Enables cooling down, waits for stabilization
        and finishes when the status first gets a stabilized setpoint """

        if not temperature_setpoint in self.temperature_range:
            raise ValueError("Invalid temperature setpoint")

        # Set the thermal timeout to several seconds (realistic
        # thermalization will happen over this timescale)
        thermal_timeout = 10 * s

        # Pull latest temperature and temperature status
        self.temperature, self.temperature_status = GetTemperatureF()

        # When cooling down, assume water cooling is present, 
        # so the fan has to be set to off 
        SetFanMode(2)

        # Set temperature and enable TEC
        SetTemperature(temperature_setpoint)
        CoolerON()

        # Wait until stable
        while 'TEMP_NOT_REACHED' in self.temperature_status:
            time.sleep(thermal_timeout)
            self.temperature, self.temperature_status = GetTemperatureF()
        while 'TEMP_STABILIZED' not in self.temperature_status:
            time.sleep(thermal_timeout)
            self.temperature, self.temperature_status = GetTemperatureF()

        self.cooling = True

        # Always return to ambient temperature on Shutdown
        SetCoolerMode(0)

    def enable_preamp(self, preamp_gain):
        """ Calls all the functions relative to the 
        preamplifier gain control. """

        if not preamp_gain in np.linspace(self.preamp_gain_range[0],
                                          self.preamp_gain_range[-1],
                                          self.number_of_preamp_gains):
            raise ValueError(f"Invalid preamp gain value..."+
                             f"valid range is {self.preamp_gain_range}")

        # Get all preamp options, match and set
        preamp_options = list(
            [GetPreAmpGain(index) for index in range(self.number_of_preamp_gains)]
        )
        SetPreAmpGain(preamp_options.index(preamp_gain))
        self.preamp_gain = preamp_gain
        self.preamp = True

    def enable_emccd(self, emccd_gain):
        """ Calls all the functions relative to the 
        emccd gain control. """

        if not emccd_gain in self.emccd_gain_range:
            raise ValueError(
                "Invalid emccd gain value, \
                             valid range is {self.emccd_gain_range}"
            )

        if not self.cooling:
            raise ValueError(
                "Please enable the temperature control before \
                enabling the EMCCD, this will prolong the lifetime of the sensor"
            )

        SetEMCCDGain(emccd_gain)
        self.emccd_gain = GetEMCCDGain()
        self.emccd = True

    def setup_vertical_shift(self, custom_option=0):
        """ Calls the functions needed to adjust the vertical
        shifting speed on the sensor for a given acquisition"""

        # Sets to the slowest one by default to mitigate noise
        # unless the acquisition has been explicitly chosen
        # to be in fast kinetics mode, for which custom methods
        # are used and a custom_option shifts between available
        # speeds, 0 is fastest, 3 is slowest.

        self.index_vs_speed, self.vs_speed = GetFastestRecommendedVSSpeed()

        if 'fast_kinetics' not in self.acquisition_mode:
            self.index_vs_speed = custom_option
            n_available_vertical_speeds = GetNumberVSSpeeds()
            if not custom_option in range(n_available_vertical_speeds):
                raise ValueError("Invalid vertical shift speed custom option value")
            else:
                self.vs_speed = GetVSSpeed(custom_option)
                SetVSSpeed(self.index_vs_speed)
                if custom_option == 0:
                    # Need to adjust Clock voltage amp
                    SetVSAmplitude(3)
        else:
            self.number_fkvs_speeds = GetNumberFKVShiftSpeeds()
            if not custom_option in range(self.number_fkvs_speeds):
                raise ValueError("Invalid vertical shift speed custom option value")
            SetFKVShiftSpeed(custom_option)
            self.vs_speed = GetFKVShiftSpeedF(custom_option)

    def setup_horizontal_shift(self, custom_option=None):
        """ Calls the functions needed to adjust the horizontal
        shifting speed on the sensor for a given acquisition"""

        # Sets to the fastest one by default to reduce download time
        # but this probably plays down on the readout noise
        intermediate_speed, self.index_hs_speed, ad_number = 0, 0, 0
        for channel in range(GetNumberADChannels()):
            n_allowed_speeds = GetNumberHSSpeeds(channel, 0)
            for speed_index in range(n_allowed_speeds):
                speed = GetHSSpeed(channel, 0, speed_index)
                if speed > intermediate_speed:
                    intermediate_speed = speed
                    self.index_hs_speed = speed_index
                    ad_number = channel

        self.hs_speed = intermediate_speed
        SetADChannel(ad_number)
        SetHSSpeed(0, self.index_hs_speed)
        # Get actual horizontal shifting (i.e. digitization) speed
        self.horizontal_shift_speed = GetHSSpeed(ad_number, 0, self.index_hs_speed)
     
    def setup_acquisition(self, added_attributes={}):
        """ Main acquisition configuration method. Available acquisition modes are
        below. The relevant methods are called with the corresponding acquisition 
        attributes dictionary, then the camera is armed and ready """
        # Override default acquisition attrs with added ones
        self.acquisition_attributes = self.default_acquisition_attrs
        for attr, val in added_attributes.items():
            self.acquisition_attributes[attr] = val
    
        self.acquisition_mode = self.acquisition_attributes['acquisition']

        if self.acquisition_attributes['preamp']:
            self.enable_preamp(self.acquisition_attributes['preamp_gain'])
        
        if self.acquisition_attributes['emccd']:
            self.enable_emccd(self.acquisition_attributes['emccd_gain'])

        # Available modes
        modes = {
            'single': 1,
            'accumulate': 2,
            'kinetic_series': 3,
            'fast_kinetics': 4,
            'run_till_abort': 5,
        }

        self.setup_trigger(**self.acquisition_attributes)

        # Configure horizontal shifting (serial register clocks)
        self.setup_horizontal_shift()

        # Configure vertical shifting (image and storage area clocks)
        self.setup_vertical_shift()

        SetAcquisitionMode(modes[self.acquisition_mode])

        # Configure added acquisition specific parameters
        if 'accumulate' in self.acquisition_mode:
            self.configure_accumulate(**self.acquisition_attributes)
        elif 'kinetic_series' in self.acquisition_mode:
            self.configure_kinetic_series(**self.acquisition_attributes)
        elif 'fast_kinetics' in self.acquisition_mode:
            self.configure_fast_kinetics(**self.acquisition_attributes)
        elif 'run_till_abort' in self.acquisition_mode:
            self.configure_run_till_abort(**self.acquisition_attributes)

        # Set exposure time, note that this may be overriden
        # by the readout, trigger or shutter timings thereafter
        SetExposureTime(self.acquisition_attributes['exposure_time'])

        self.setup_shutter(**self.acquisition_attributes)
        self.setup_readout(**self.acquisition_attributes)

        # Get actual timings
        self.exposure_time, self.accum_timing, self.kinetics_timing = GetAcquisitionTimings()
    
        if 'fast_kinetics' in self.acquisition_mode:
            self.exposure_time = GetFKExposureTime()
        
        # Arm sensor
        self.armed = True

        self.keepClean_time = GetKeepCleanTime()
        # Note: This call breaks in FK mode... unknown reasons
        if 'fast_kinetics' not in self.acquisition_mode:
            self.readout_time = GetReadOutTime()

        else:
            # Made up number, somehow FK doesn't work with GetReadOutTime()
           self.readout_time = 1000.0 

       
    def configure_accumulate(self, **attrs):
        """ Takes a sequence of single scans and adds them together """
    
        SetNumberAccumulations(attrs['number_accumulations'])
        
        # In External Trigger mode the delay between each scan making up
        # the acquisition is not under the control of the Andor system but
        # is synchronized to an externally generated trigger pulse.
        if 'internal' in attrs['trigger']:
            SetAccumulationCycleTime(attrs['accumulation_period'])


    def configure_kinetic_series(self, **attrs):
        """ Captures a sequence of single scans, or possibly, depending on 
        the camera, a sequence of accumulated scans """

        SetNumberKinetics(attrs['number_kinetics'])

        if attrs['trigger'] == 'internal' and attrs['number_kinetics'] > 1:
            SetKineticCycleTime(attrs['kinetics_period'])

        # Setup accumulations for the series if necessary
        if attrs['number_accumulations'] > 1:
            self.configure_accumulate(**attrs)
        else:
            SetNumberAccumulations(1)

    def configure_fast_kinetics(self, **attrs):
        """ Special readout mode that uses the actual sensor as a temporary 
        storage medium and allows an extremely fast sequence of images to be 
        captured """

        fk_modes = {'FVB': 0, 'full_image': 4}
    
        if 'exposed_rows' not in attrs.keys():
            # Assume that fast kinetics series fills CCD maximally,
            # and compute the number of exposed rows per exposure
            exposed_rows = int(self.y_size / attrs['number_kinetics'])
        else:
            exposed_rows = attrs['exposed_rows']

        SetFastKineticsEx(
            exposed_rows,
            attrs['number_kinetics'],
            attrs['exposure_time'],
            fk_modes[attrs['readout']],
            attrs['xbin'],
            attrs['ybin'],
            attrs['v_offset'],
        )

    def configure_run_till_abort(self, **attrs):
        """ Continually performs scans of the CCD until aborted """
        if 'internal' in attrs['trigger']:
            SetKineticCycleTime(0)
        else:
            raise Exception("Can't run_till_abort mode if external trigger")

    def setup_trigger(self, **attrs):
        """ Sets different aspects of the trigger"""

        # Available modes
        modes = {
            'internal': 0,
            'external': 1,
            'external_start': 6,
            'external_exposure': 7,
        }

        edge_modes = {'rising': 0, 'falling': 1}

        SetTriggerMode(modes[attrs['trigger']])

        # Specify edge if invertible trigger capability is present
        if 'INVERT' in self.trig_capability:
            SetTriggerInvert(edge_modes[attrs['trigger_edge']])

        if attrs['trigger'] == 'external':
            SetFastExtTrigger(1)

    def setup_shutter(self, **attrs):
        """ Sets different aspects of the shutter and exposure"""
    
        # Available modes
        modes = {
            'auto': 0,
            'perm_open': 1,
            'perm_closed': 2,
            'open_FVB_series': 4,
            'open_any_series': 5,
        }

        shutter_outputs = {'low': 0, 'high': 1}

        # TODO: Add SetShutterEX support for labscript

        SetShutter(
            shutter_outputs[attrs['shutter_output']],
            modes[attrs['int_shutter_mode']],
            attrs['shutter_t_close'] + int(round(attrs['exposure_time'] / ms)),
            attrs['shutter_t_open'],
        )

    def setup_readout(self, **attrs):
        """ Sets different aspects of the data readout, including 
        image shape, readout mode """

        # Available modes
        modes = {
            'FVB': 0,
            'multi_track': 1,
            'random_track': 2,
            'single_track': 3,
            'full_image': 4,
        }

        SetReadMode(modes[attrs['readout']])

        if attrs['readout'] == 'single_track':
            SetSingleTrack(attrs['center_row'], attrs['height'])

        # For full vertical binning setup a 1d-array shape
        if attrs['readout'] == 'FVB':
            attrs['width'] = 1

        self.image_shape = (
            int(attrs['number_kinetics']),
            int(attrs['height']),
            int(attrs['width']),
        )
        
        if (
            self.acquisition_mode == 'kinetic_series'
            and self.acquisition_attributes['crop']
        ):
            SetOutputAmplifier(0)
            SetFrameTransferMode(1)
            SetImage(
                attrs['xbin'],
                attrs['ybin'],
                attrs['left_start'],
                attrs['width'] + attrs['left_start'] - 1,
                attrs['bottom_start'],
                attrs['height'] + attrs['bottom_start'] - 1,
            )
            SetIsolatedCropModeEx(
                int(1),
                int(attrs['height']),
                int(attrs['width']),
                attrs['ybin'],
                attrs['xbin'],
                attrs['left_start'],
                attrs['bottom_start'],
            )
        else:
            SetFrameTransferMode(0)
            SetIsolatedCropModeEx(
                int(0),
                int(attrs['height']),
                int(attrs['width']),
                attrs['ybin'],
                attrs['xbin'],
                attrs['left_start'],
                attrs['bottom_start'],
            )
            SetImage(
                attrs['xbin'],
                attrs['ybin'],
                attrs['left_start'],
                attrs['width'] + attrs['left_start'] - 1,
                attrs['bottom_start'],
                attrs['height'] + attrs['bottom_start'] - 1,
            )

    def acquire(self):
        """ Carries down the acquisition, if the camera is armed and
        waits for an acquisition event for acquisition timeout (has to be
        in milliseconds), default to 5 seconds """
    
        acquisition_timeout = self.acquisition_attributes['acquisition_timeout']

        def homemade_wait_for_acquisition():
            self.acquisition_status = ''
            start_wait = time.time()
            while self.acquisition_status != 'DRV_IDLE':
                self.acquisition_status = GetStatus()
                t0 = time.time() - start_wait
                if t0 > acquisition_timeout * ms:
                    rich_print(
                        "homemade_wait_for_acquisition: timeout occured",
                        color='firebrick',
                    )
                    break
                time.sleep(0.05)
            if self.chatty:
                rich_print(
                    f"Leaving homemade_wait with status {self.acquisition_status} ",
                    color='goldenrod',
                )
                rich_print(
                    f"homemade_wait_for_acquisition: elapsed time {t0/ms} ms, out of max {acquisition_timeout} ms",
                    color='goldenrod',
                )
                                                            
        if not self.armed:
            raise Exception("Cannot start acquisition until armed")
        else:
            self.acquisition_status = GetStatus()
            if 'DRV_IDLE' in self.acquisition_status:
                StartAcquisition()
                if self.chatty:
                    rich_print(
                        f"Waiting for {acquisition_timeout} ms for timeout ...",
                        color='yellow',
                    )
                homemade_wait_for_acquisition()
            
            # Last chance, check if the acquisition is finished, update
            # acquisition status otherwise, abort and raise an error

            self.acquisition_status = GetStatus()
            self.armed = False

            if self.acquisition_status != 'DRV_IDLE':
                AbortAcquisition()
                raise AndorException('Acquisition aborted due to timeout')

    def download_acquisition(self,):
        """ Download buffered acquisition """
        shape = (
            self.image_shape[0],
            int(self.image_shape[1] / int(self.acquisition_attributes['ybin'])),
            int(self.image_shape[2] / int(self.acquisition_attributes['xbin'])),
        )
    
        # Lets see what we have in memory
        available_images = GetNumberAvailableImages()

        if (available_images[1] - available_images[0]) + 1 == shape[0]:
            data = GetAcquiredData(shape).reshape(shape)
        else:
            print(
                "### Incorrect number of images to download:",
                available_images,
                " expecting: ",
                self.image_shape[0],
            )
            data = np.zeros(shape)

        FreeInternalMemory()

        return data

    def abort_acquisition(self):
        """Abort"""
        if self.chatty:
            rich_print("Debug: Abort Called", color='yellow')
        AbortAcquisition()

    def shutdown(self):
        """ Shuts camera down, if unarmed """
        if self.armed:
            raise ValueError(
                "Cannot shutdown while the camera is armed, "
                + "please finish or abort the current acquisition before shutdown"
            )
        else:
            ShutDown()
        
if __name__ in '__main__':
    pass
#     cam = AndorCam()
    
     # First test should arm with default attrs and go
#     cam.setup_acquisition(added_attributes={'exposure_time':25*ms,})
#     cam.snap()
#     single_acq_image = cam.grab_acquisition()
#    
#      # Second test, 3-shot kinetic series, internal trigger,
#      # similar to absorption imaging series
#     internal_kinetics_attrs = {
#     'exposure_time':20*ms,
#     'acquisition':'kinetic_series',
#     'number_kinetics':3,
#     'kinetics_period':20*ms,
#     'readout':'full_image',
#     'int_shutter_mode':'perm_open',
#     }
#     cam.setup_acquisition(internal_kinetics_attrs)
#     cam.snap()
#     kinetics_series_images = cam.grab_acquisition()
#    
#    
#     # Third test, 10-shot fast kinetics, internal trigger and no binning.
#     fast_kinetics_attrs = {
#     'exposure_time':1*ms,
#     'acquisition':'fast_kinetics',
#     'number_kinetics':16,
#     'readout_shape':(1, cam.x_size, cam.y_size),
#     'readout':'full_image',
#     'int_shutter_mode':'perm_open',
#     }
#     cam.setup_acquisition(fast_kinetics_attrs)
#     cam.snap()
#     fast_kinetics_image = cam.grab_acquisition()
#    
#     import matplotlib.pyplot as plt
#     plt.figure()
#     plt.imshow(single_acq_image[0], cmap='seismic')
#    
#     plt.figure()
#     ax = plt.subplot(311)
#     ax.imshow(kinetics_series_images[0], cmap='seismic')
#     ax = plt.subplot(312)
#     ax.imshow(kinetics_series_images[1], cmap='seismic')
#     ax = plt.subplot(313)
#     ax.imshow(kinetics_series_images[2], cmap='seismic')
#    
#     plt.figure()
#     plt.imshow(fast_kinetics_image[0], cmap='seismic')
#    
