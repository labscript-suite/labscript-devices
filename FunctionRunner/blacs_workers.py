#####################################################################
#                                                                   #
# /labscript_devices/FunctionRunner/blacs_worker.py                 #
#                                                                   #
# Copyright 2019, Monash University and contributors                #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
import os
from time import monotonic
import numpy as np
import labscript_utils.h5_lock
import h5py
from blacs.tab_base_classes import Worker
import runmanager
import runmanager.remote
from zprocess import rich_print
from .utils import deserialise_function

BLUE = '#66D9EF'
PURPLE = '#AE81FF'
GREEN = '#A6E22E'
GREY = '#75715E' 

def deserialise_function_table(function_table, device_name):
    table = []
    for t, name, source, args, kwargs in function_table:
        if t == -np.inf:
            t = 'start'
        elif t == np.inf:
            t = 'stop'
        # We deserialise the functions in a namespace with the given __name__ and
        # __file__ so that if the user instantiates a lyse.Run object, that the results
        # will automatically be saved to a results group with the name of this
        # FunctionRunner, since lyse.Run inspects the filename to determine this.
        function, args, kwargs = deserialise_function(
            name, source, args, kwargs, __name__=device_name, __file__=device_name
        )
        table.append((t, name, function, args, kwargs))
    return table


class ShotContext(object):
    def __init__(self, h5_file, device_name):
        self.h5_file = h5_file
        self.device_name = device_name
        self.globals = runmanager.get_shot_globals(h5_file)


class FunctionRunnerWorker(Worker):
    def program_manual(self, values):
        return {}

    def transition_to_buffered(self, device_name, h5_file, initial_values, fresh):
        rich_print(f"====== new shot: {os.path.basename(h5_file)} ======", color=GREEN)
        with h5py.File(h5_file, 'r') as f:
            group = f[f'devices/{self.device_name}']
            if 'FUNCTION_TABLE' not in group:
                self.function_table = None
                rich_print("[no functions]", color=GREY)
                return {}
            function_table = group['FUNCTION_TABLE'][:]

        self.function_table = deserialise_function_table(
            function_table, self.device_name
        )
        self.shot_context = ShotContext(h5_file, self.device_name)
        if self.function_table[0][0] != 'start':
            rich_print("no start functions", color=GREY)
            return {}
        rich_print("[running start functions]", color=PURPLE)
        while self.function_table:
            t, name, function, args, kwargs = self.function_table[0]
            if t != 'start':
                break
            del self.function_table[0]
            rich_print(f"  t={t}: {name}()", color=BLUE)
            function(self.shot_context, t, *args, **kwargs)
        rich_print("[finished start functions]", color=PURPLE)
        return {}

    def transition_to_manual(self):
        if self.function_table is None:
            return True
        elif not self.function_table:
            rich_print("no stop functions", color=GREY)
            return True
        rich_print("[running stop functions]", color=PURPLE)
        while self.function_table:
            t, name, function, args, kwargs = self.function_table.pop(0)
            assert t == 'stop'
            rich_print(f"  t={t}: {name}()",color=BLUE)
            function(self.shot_context, t, *args, **kwargs)
        rich_print("[finished stop functions]", color=PURPLE)

        return True

    def shutdown(self):
        return

    def abort_buffered(self):
        return self.transition_to_manual()

    def abort_transition_to_buffered(self):
        return True
