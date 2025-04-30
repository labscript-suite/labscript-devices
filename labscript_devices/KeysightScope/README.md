# ------------------------- How to use the oscilloscope implementation -------------------------

# ------------------------- Supported models 
* Currently supported models: EDUX1052A, EDUX1052G, DSOX1202A, DSOX1202G, DSOX1204A, DSOX1204G

# ------------------------- Current possible utilization

### Triggering 
* Triggering must be performed via the external trigger input.
* Data is read from the channels currently displayed on the oscilloscope.

### Oscilloscope shot configuration
* You can configure the oscilloscope manually and then upload the configuration to labscript using the BLACS GUI interface.

# ------------------------- First settings for your Keysight oscilloscope 

1. In the file `Keysightscope/models/Keysight_dsox1202g`, you’ll find an example containing the dictionary:  
   * `osci_capabilities`: defines device-specific capabilities.

2. To support your specific oscilloscope model:
   * Copy this example file into the same folder.
   * Edit the `osci_capabilities` dictionary to match your oscilloscope’s specifications.

------------------------- !!! Important !!! -------------------------
1. The filename **must** begin with `"Keysight"` to be detected properly,  
   e.g., `Keysightscope/models/Keysight_dsox1202g`

2. Do **not** rename the dictionary `osci_capabilities`.

3. The serial number of your oscilloscope must be included in the `osci_capabilities` dictionary.

# ------------------------- Example Script

### In the Python connection table

```python
KeysightScope(
    name="osci_keysight",
    serial_number="CN61364200",
    parent_device=osci_Trigger  # parent_device must be a digital output initialized as Trigger(...)
)
```

### In the python experiment file
```python
start()
t = 0

osci_keysight.set_config(3)         # Must be called once at the start of each experiment shot      

trigger_duration = 1e-4             # Example trigger duration
osci_keysight.trigger_at(t=t, duration=trigger_duration)

t += trigger_duration
stop(t)
```