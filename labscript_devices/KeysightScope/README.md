#  Keysight oscilloscope implementation 

## Supported models 
* Currently supported models: EDUX1052A, EDUX1052G, DSOX1202A, DSOX1202G, DSOX1204A, DSOX1204G

## Current possible utilization

### Triggering 
* The oscilloscope is to be used in trigger mode (Single mode).
* Triggering must be performed via the external trigger input.
* Data is read from the channels currently displayed on the oscilloscope.

### Oscilloscope configuration
* You can configure the oscilloscope manually and then upload the configuration to labscript using the BLACS GUI interface, as shown in the following example:

![alt text](<Screenshot_BLACS_tab.png>)

* **1** By pressing `activate` on a spot index (in this example, Spot 0), the oscilloscope loads the configuration state saved in that spot, and the tab number lights up red.

* **2** Once a specific spot is activated,it becomes editable. You can either:
   * Manually change the oscilloscope settings directly on the device, then click `load and save` in the BLACS tab to import and save the updated configuration for that spot.
   * Or, click `reset to default` to load the default oscilloscope configuration.

* **3** This zone gives an overview of the most important setting parameters for the currently selected (green highleted, not necessarly activated) tab.


##  Example Script

### In the Python connection table

```python
KeysightScope(
    name="osci_keysight",
    serial_number="CN61364200",
    parent_device=osci_Trigger      # parent_device must be a digital output initialized as Trigger(...)
)
```

### In the python experiment file
There are two main functions to use in the experiment scipt:

* `set_config( spot_index : int or string )` : The oscilloscope has ten different spots where it saves its global settings. set_config(spot_index) must be called at the beginning of the experiment script with the desired spot_index to initialize the oscilloscope with the corresponding configuration for the shot.


* `trigger_at( t=t, duration=trigger_duration )` : This function allows the parent device (of type Trigger()) to trigger the oscilloscope for the specified trigger_duration. During this short period, data will be read from the displayed channels.

```python
start()
t = 0

osci_keysight.set_config(3)         # Must be called once at the start of each experiment shot      

trigger_duration = 1e-4             # Example trigger duration
osci_keysight.trigger_at(t=t, duration=trigger_duration)

t += trigger_duration
stop(t)
```