#####################################################################
#                                                                   #
# /labscript_devices/FunctionRunner/utils.py                        #
#                                                                   #
# Copyright 2019, Monash University and contributors                #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

import inspect
import textwrap
from types import FunctionType
from labscript_utils import dedent
from labscript_utils.properties import serialise, deserialise


def serialise_function(function, *args, **kwargs):
    """Serialise a function based on its source code, and serialise the additional args
    and kwargs that it will be called with. Raise an exception if the function signature
    does not begin with (shot_context, t) or if the additional args and kwargs are
    incompatible with the rest of the function signature"""
    signature = inspect.signature(function)
    if not tuple(signature.parameters)[:2] == ('shot_context', 't'):
        msg = """function must be defined with (shot_context, t, ...) as its first two
            arguments"""
        raise ValueError(dedent(msg))
    # This will raise an error if the arguments do not match the function's call
    # signature:
    _ = signature.bind(None, None, *args, **kwargs)

    # Enure it's a bona fide function and not some other callable:
    if not isinstance(function, FunctionType):
        msg = f"""callable of type {type(function)} is not a function. Only functions
            can be used, not other callables"""
        raise TypeError(dedent(msg))

    # Serialise the function, args and kwargs:
    source = textwrap.dedent(inspect.getsource(function))
    args = serialise(args)
    kwargs = serialise(kwargs)

    return function.__name__, source, args, kwargs


def deserialise_function(
    name, source, args, kwargs, __name__=None, __file__='<string>'
):
    """Deserialise a function that was serialised by serialise_function. Optional
    __name__ and __file__ arguments set those attributes in the namespace that the
    function will be defined."""
    args = deserialise(args)
    kwargs = deserialise(kwargs)
    code = compile(source, '<string>', 'exec', dont_inherit=True,)
    namespace = {'__name__': __name__, '__file__': __file__}
    exec(code, namespace)
    return namespace[name], args, kwargs
