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
from __future__ import division, unicode_literals, print_function, absolute_import
from labscript_utils import PY2

if PY2:
    str = unicode

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


def port_and_line_to_PFI(port, line, ports):
    """For a given port and line number, and a dictionary of ports and their
    capabilities (as passed to NI_DAQmx as the ports keyword argument), compute the PFI
    terminal that corresponds to that port and line, under the assumption that the PFI
    terminals begin as PFI0 on the first line of the first port that does not support
    buffered output and count upward."""
    n_ports = len(ports)
    PFI_num = 0
    for port_num in range(n_ports):
        capabilities = ports['port%d' % port_num]
        if capabilities['supports_buffered']:
            continue
        elif port_num != port:
            PFI_num += capabilities['num_lines']
        elif line < capabilities['num_lines']:
            PFI_num += line
            return 'PFI%d' % PFI_num
    msg = "port%d/line%d does not correspond to an unbuffered digital output"
    raise ValueError(msg % (port, line))


def port_line_to_hardware_name(port, line, ports):
    """For a given port and line number, and a dictionary of ports and their
    capabilities (as passed to NI_DAQmx as the ports keyword argument), generate a
    string description of the connection like 'port1/line0 (PFI0)'. If the line is on a
    port capable of buffered output, the result will not have the PFI part appended. The
    PFI number used assumes that the PFI terminals begin as PFI0 on the first line of
    the first port that does not support buffered output and count upward."""
    port_str = 'port%d'  % port
    hardware_name = '%s/line%d' % (port_str, line)
    if not ports[port_str]['supports_buffered']:
        PFI_conn = port_and_line_to_PFI(port, line, ports)
        hardware_name += ' (%s)' % PFI_conn
    return hardware_name
