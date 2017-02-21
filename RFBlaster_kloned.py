import socket
import time

# Parameters
address = '192.168.1.3'
port = 8009
timeout = 10

# Restart kloned
print 'Connecting to %s...' %  address
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(timeout)

def has_reply(s, timeout=0):
    """Checks whether a reply is waiting to be be read"""
    socklist = select.select([s], [], [], timeout)
    return len(socklist[0]) > 0

def flush(s, timeout=0, buffer=1024):
    """Removes and pending data to be received from the socket, and returns the number of bytes flushed"""
    n = 0
    while has_reply(s, timeout):
        n += len(s.recv(buffer))
    return n

def read(s, buffer=1024):
    """Read data from the socket"""
    data = s.recv(buffer)
    while has_reply(s, timeout=0):
        data += s.recv(buffer)
    return data

try:
    s.connect((address, 8009))
    print 'Connected!'
    if True:
        print 'Respawning netcat...'
        s.sendall('nohup nc -l -p 8009 -e /bin/sh &')
        # response = read(s)
        # print(response)
        time.sleep(0.5)
    if True:
        print 'Trying to start/restart kloned...'
        s.sendall('nohup ./startup/klone_start.sh &')
        # response = read(s)
        # print(response)
        time.sleep(0.5)
        s.shutdown(socket.SHUT_WR)
    print 'Finished. Closing socket.'
    s.close()
except socket.error as e:
    print 'Unable to connect to %s.' % address
    # ps|grep kloned|grep -v grep > /dev/null