
from labscript import Device, LabscriptError, set_passed_properties ,LabscriptError, AnalogIn

class ScopeChannel(AnalogIn):
    """Subclass of labscript.AnalogIn that marks an acquiring scope channel.
    """
    description = 'Scope Acquisition Channel Class'

    def __init__(self, name, parent_device, connection):
        """This instantiates a scope channel to acquire during a buffered shot.

        Args:
            name (str): Name to assign channel
            parent_device (obj): Handle to parent device
            connection (str): Which physical scope channel is acquiring.
                              Generally of the form \'Channel n\' where n is
                              the channel label.
        """
        Device.__init__(self,name,parent_device,connection)
        self.acquisitions = []

    def acquire(self):
        """Inform BLACS to save data from this channel.
        Note that the parent_device controls when the acquisition trigger is sent.
        """
        if self.acquisitions:
            raise LabscriptError('Scope Channel {0:s}:{1:s} can only have one acquisition!'.format(self.parent_device.name,self.name))
        else:
            self.acquisitions.append({'label': self.name})