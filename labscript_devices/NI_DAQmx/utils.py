#####################################################################
#                                                                   #
# /NI_DAQmx/utils.py                                                #
#                                                                   #
# Copyright 2018, Monash University, JQI, Christopher Billington    #
#                                                                   #
# This file is part of the module labscript_devices, in the         #
# labscript suite (see http://labscriptsuite.org), and is           #
# licensed under the Simplified BSD License. See the license.txt    #
# file in the root of the project for the full license.             #
#                                                                   #
#####################################################################
from labscript_utils import dedent


def split_conn_DO(connection):
    """Return the port and line number of a connection string such as 'port0/line1 as
    two integers, or raise ValueError if format is invalid. Accepts connection strings
    such as port1/line0 (PFI0) - the PFI bit is just ignored"""
    try:
        if len(connection.split()) == 2:
            # Just raise a ValueError if the second bit isn't of the form ('PFI<n>')
            connection, PFI_bit = connection.split()
            if not (PFI_bit.startswith('(') and PFI_bit.endswith(')')):
                raise ValueError
            split_conn_PFI(PFI_bit[1:-1])
        port, line = [int(n) for n in connection.split('port', 1)[1].split('/line')]
    except (ValueError, IndexError):
        msg = """Digital output connection string %s does not match format
            'port<N>/line<M>' for integers N, M"""
        raise ValueError(dedent(msg) % str(connection))
    return port, line


def split_conn_AO(connection):
    """Return analog output number of a connection string such as 'ao1' as an
    integer, or raise ValueError if format is invalid"""
    try:
        return int(connection.split('ao', 1)[1])
    except (ValueError, IndexError):
        msg = """Analog output connection string %s does not match format 'ao<N>' for
            integer N"""
        raise ValueError(dedent(msg) % str(connection))


def split_conn_AI(connection):
    """Return analog input number of a connection string such as 'ai1' as an
    integer, or raise ValueError if format is invalid"""
    try:
        return int(connection.split('ai', 1)[1])
    except (ValueError, IndexError):
        msg = """Analog input connection string %s does not match format 'ai<N>' for
            integer N"""
        raise ValueError(dedent(msg) % str(connection))


def split_conn_PFI(connection):
    """Return PFI input number of a connection string such as 'PFI0' as an
    integer, or raise ValueError if format is invalid"""
    try:
        return int(connection.split('PFI', 1)[1])
    except (ValueError, IndexError):
        msg = "PFI connection string %s does not match format 'PFI<N>' for integer N"
        raise ValueError(msg % str(connection))


def split_conn_port(connection):
    """Return port number of a string such as 'port0' as an
    integer, or raise ValueError if format is invalid"""
    try:
        return int(connection.split('port', 1)[1])
    except (ValueError, IndexError):
        msg = "port string %s does not match format 'port<N>' for integer N"
        raise ValueError(msg % str(connection))
