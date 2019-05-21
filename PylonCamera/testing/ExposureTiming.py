#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  ExposureTiming.py

def set_attribute(camera, name, value):
    """Set the value of the attribute of the given name to the given value"""
    try:
        camera.GetNodeMap().GetNode(name).SetValue(value)
    except Exception as e:
        # Add some info to the exception:
        msg = f"failed to set attribute {name} to {value}"
        raise Exception(msg) from e

if __name__ == '__main__':
    import sys
    import argparse
    
    try:
        from pypylon import pylon, genicam
    except:
        print('Failed to import pypylon. Is it installed correctly?')
        raise
    
    help_text = '''
    Syntax: python ExposureTiming.py [camera_sn]'''
    
    parser = argparse.ArgumentParser(description=help_text)
    
    parser.add_argument('-sn','--serial',action='store',
                        help='Camera Serial number to connect to. If not provided, list available cameras.',
                        default=None)
    
    args = parser.parse_args()
    
    factory = pylon.TlFactory.GetInstance()
    
    if args.serial == None:
        devices = factory.EnumerateDevices()
        for i,camera in enumerate(devices):
            camera = pylon.InstantCamera(factory.CreateDevice(camera))
            caminfo = camera.GetDeviceInfo()
            print(f'{i} : {caminfo.GetModelName()}, SN:{caminfo.GetSerialNumber()}')
            camera.Close()
        sys.exit(0)
    
    try:
        sn = pylon.CDeviceInfo()
        sn.SetSerialNumber(args.serial)
        camera = pylon.InstantCamera(factory.CreateDevice(sn))
        camera.Open()
    except:
        raise
    
    # set standard default configuration from server
    camera.RegisterConfiguration(pylon.SoftwareTriggerConfiguration(),
                        pylon.RegistrationMode_ReplaceAll, pylon.Cleanup_Delete)
    
    # put frame readout affecting settings here, otherwise just use the default
    settings_dict = {'ExposureTime':9000,
                     'ExposureMode':'Timed',
			         'ExposureAuto':'Off',
			         'PixelFormat':'Mono12',
			         'ShutterMode':'Global',
                     'Width':1280,
                     'Height':960,
                     'OffsetX':8,
                     'OffsetY':3
                     }
    exp_time = settings_dict['ExposureTime']
    ROIx = ['Width','OffsetX']
    ROIy = ['Height','OffsetY']
    if set(ROIx).issubset(settings_dict):
        # setting ROI width and offset requires logic
        if settings_dict['OffsetX'] <= (camera.WidthMax() - camera.Width()):
            ROIx.reverse()
        ROIx_settings = [settings_dict.pop(k) for k in ROIx]
        for k,v in zip(ROIx,ROIx_settings):
            print(f'Setting {k} to {v}')
            set_attribute(camera,k,v)
        
    if set(ROIy).issubset(settings_dict):
        # setting ROI width and offset requires logic
        if settings_dict['OffsetY'] <= (camera.HeightMax() - camera.Height()):
            ROIy.reverse()
        ROIy_settings = [settings_dict.pop(k) for k in ROIy]
        for k,v in zip(ROIy,ROIy_settings):
            print(f'Setting {k} to {v}')
            set_attribute(camera,k,v)

    for k,v in settings_dict.items():
        try:
            print(f'Setting {k} to {v}')
            set_attribute(camera,k,v)
        except Exception as e:
            raise Exception(f'Failed to set {k} to {v}') from e
            
    # get timing parameters given the current settings
    if camera.IsGigE():
        readout_time = camera.ReadoutTimeAbs()
        max_frame_rate = camera.ResultingFrameRateAbs()
        frame_rate_period = camera.ResultingFramePeriodAbs()
    else:
        readout_time = camera.SensorReadoutTime()
        max_frame_rate = camera.ResultingFrameRate()
        frame_rate_period = 1/max_frame_rate
        
    print(f"\n\tSensor Readout Time is {readout_time} us")
    print(f"\tMax Possible Framerate is {max_frame_rate} Hz")
    
    # overlapped mode is also possible if second exposure starts before 
    # the first exposure finishes reading out and ends after the readout is
    # complete
    
    if exp_time >= readout_time:
        # second exposure will always finish after readout
        # min time between triggers is just the exposure time
        min_time_between_triggers = exp_time
    else:
        min_time_between_triggers = readout_time - 2*exp_time
    
    print(f"\tTime between trigger starts must be > {min_time_between_triggers} us")
    
    camera.Close()
        
