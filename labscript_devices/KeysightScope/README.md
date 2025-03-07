

# ------------------------- How to use the oscilloscope implementation -------------------------


# ------------------------- First settings 
In the file Keysightscope/models/example_to_copy you can find a file containing two dictionaries: 
* osci_shot_configuration : contains the configuration that the oscilloscope will use for every shot
* osci_capabilities : contains device specific capabilities 

Copy-paste this file in the same folder and change it according to your goal.
------------------------- !!! Important !!! -------------------------
1. The name of the new file must start with "Keysight", or the program will not detect it,
e.g.  Keysightscope/models/Keysight_dsox1202g
2. Don't change the name of the dictionaries: osci_shot_configuration and osci_capabilities
3. In the dictionary osci_capabilities you can give any description to the osci. 
The description will then be used across the program to interact with the osci


# ------------------------- In the connection table file
There are two ways with which we can trigger the oscilloscope.

# Method 1 : Triggering on the channels 
KeysightScope(name="Keysight", 
                parent_device = None,
                parentless=True,
                description="Example Osci")

* Advantages    : We can trigger on AnalogOut devices
* Disadvantages : We can not manually trigger. 
 

------------------------- !!! Important !!! -------------------------
KeysightScope is a  Triggerable device and accroding to Labscript we can use it parentless. 
However, the Labscript code showed (class TriggerableDevice), that this is not true and we have to make some minor case handling before beeing able to use our scope as in methode 1.

Following two changes are required to the class TriggerableDevice in the file labscript.labscript.labscript.py
You dont have to understand the code, just add the marked lines

### First change
class TriggerableDevice(Device):
        def __init__(...): 
        if None in [parent_device, connection] and not parentless:
            raise LabscriptError('No parent specified. If this device does not require a parent, set parentless=True')
        if isinstance(parent_device, Trigger):
            if self.trigger_edge_type != parent_device.trigger_edge_type:
                raise LabscriptError('Trigger edge type for %s is \'%s\', ' % (name, self.trigger_edge_type) + 
                                      'but existing Trigger object %s ' % parent_device.name +
                                      'has edge type \'%s\'' % parent_device.trigger_edge_type)
            self.trigger_device = parent_device
        elif parent_device is not None:
            # Instantiate a trigger object to be our parent:
            self.trigger_device = Trigger(name + '_trigger', parent_device, connection, self.trigger_edge_type)
            parent_device = self.trigger_device
            connection = 'trigger'
        elif parent_device is None:             ######################### -> These two lines are new
            self.trigger_device = parent_device ######################### -> Add the last two lines

### second change
In the same class in the function do_checks

def do_checks(self):
    if self.trigger_device is not None:         ######################### -> Add only the first line 
        for device in self.trigger_device.child_devices:
            if device is not self:
                ......


# Method 2: Triggering on the external trigger 
KeysightScope(name="Keysight", parent_device=p00,connectin = ""trigger, description="Example Osci")

* Advantages    : We can manually trigger
* Disadvantages : We need to reserve a DigitalOut for the trigger functionality in the experiment 



 # ------------------------- In the experimental file
 # Method 1 : Triggering on the channels 
No Need for change 

# Method 2: Triggering on the external trigger 
You need to manually request the trigger by going high. 
In our case ->  p00.go_high(t)

# ------------------------- To Add a new Device 
Currenlty 19.02.2025
To add a new device, you need to:
1. Copy this folder 
2. Add a new sheet for the osci as shown above
3. Change the description in the files KeysightScope and labscript_devices
4. Minor adjustments to some import headers

(Goal in the future : Implementation that resembles the Ni-CArds., where we would need only one folder for all the scopes)
