Implementation 


# ------------------------- To Add a new Device 
currenlty 19.02.2025
to add a new device you need to:
1. copy this folder 
2. add a new sheet for the osci as shown in the folder 
3. change the description in the files KeysightScope and labscript_devices


# ------------------------- In the connection table file 

# Methode 1 : Triggering on the channels 
KeysightScope(name="Keysight", parentless=True, description="important description")


# Methode 2: Triggering on the external trigger 
KeysightScope(name="Keysight", parent_device=p00, description="important description")

 

 # ------------------------- In the experimental file
 For Methode 1 : No Need for change 

For Methode 2 : You need to manually request the trigger by going high 
In our case ->  p00.go_high(t)