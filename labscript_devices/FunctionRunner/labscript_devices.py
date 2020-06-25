import numpy as np
from labscript import Device
from labscript_utils import dedent
import labscript_utils.h5_lock, h5py
from .utils import serialise_function


class FunctionRunner(Device):
    """A labscript device to run custom functions before, after, or during (not yet
    implemented) the experiment in software time"""

    def __init__(self, name, **kwargs):
        Device.__init__(self, name=name, parent_device=None, connection=None, **kwargs)
        self.functions = []
        self.BLACS_connection = name

    def add_function(self, t, function, *args, **kwargs):
        """Add a function to be run at time t. If t='start', then the function will run
        prior to the shot beginning, and if t='stop', it will run after the experiment
        has completed. Tip: use `start_order` and `stop_order` keyword arguments when
        instantiating this device to control the relative order that its 'start' and
        'stop' functions run compared to the transition_to_manual and
        transition_to_buffered functions of other devices. Multiple functions added to
        run at the same time will be run in the order added. Running functions mid-shot
        in software time is yet to be implemented.

        The function must have a call signature like the following:

            def func(shot_context, t, ...):
                ...

        When it is called, a ShotContext instance will be passed in as the first
        argument, and the time at which the function was requested to run as the second
        argument. The ShotContext instance will be the same for all calls for the same
        shot, so it can be used to store state for that shot (but not from one shot to
        the next), the same way you would use the 'self' argument of a method to store
        state in an instance. As an example, you might set shot_context.serial to be an
        open serial connection to a device during a function set to run at t='start',
        and refer back to it in subsequent functions to read and write data. Other than
        state stored in shot_context, the functions must be self-contained, containing
        any imports that they need.

        This object has a number of attributes:

        - self.globals: the shot globals
        - self.h5_file: the filepath to the shot's HDF5 file
        - self.device_name: the name of this FunctionRunner

        If you want to save raw data to the HDF5 file at the end of a shot, the
        recommended place to do it is within the group 'data/<device_name>', for
        example:

            with h5py.File(self.h5_file, 'r+') as f:
                data_group = f['data'].create_group(self.device_name)
                # save datasets/attributes within this group

        Or, if you are doing analysis and want to save results that will be accessible
        to lyse analysis routines in the usual way, you can instantiate a lyse.Run
        object and call Run.save_result() etc:

            import lyse
            run = lyse.Run(shot_context.h5_file)
            run.save_result('x', 7)

        The group that the results will be saved to, which is usually the filename of
        the lyse analysis routine, will instead be the device name of the
        FunctionRunner.

        The use case for which this device was implemented was to update runmanager's
        globals immediately after a shot, based on measurement data, such that
        just-in-time compiled shots imme. This is done by calling the runmanager remote API
        from within a function to be run at the end of a shot, like so:

            import runmanager.remote
            runmanager.remote.set_globals({'x': 7})

        """
        name, source, args, kwargs = serialise_function(function, *args, **kwargs)
        if t == 'start':
            t = -np.inf
        elif t == 'stop':
            t = np.inf
        else:
            t = float(t)
            msg = """Running functions mid-experiment not yet implemented. For now, t
                must be "start" or "stop"."""
            raise NotImplementedError(dedent(msg))
        self.functions.append((t, name, source, args, kwargs))

    def generate_code(self, hdf5_file):
        # Python's sorting is stable, so items with equal times will remain in the order
        # they were added
        self.functions.sort()
        vlenstr = h5py.special_dtype(vlen=str)
        table_dtypes = [
            ('t', float),
            ('name', vlenstr),
            ('source', vlenstr),
            ('args', vlenstr),
            ('kwargs', vlenstr),
        ]
        function_table = np.array(self.functions, dtype=table_dtypes)
        group = self.init_device_group(hdf5_file)
        if self.functions:
            group.create_dataset('FUNCTION_TABLE', data=function_table)
