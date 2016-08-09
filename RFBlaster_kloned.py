import socket
import time

# Parameters
address = '192.168.1.5'
port = 8009
timeout = 10

# Restart kloned
print 'Connecting to %s...' %  address
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(timeout)

try:
    s.connect((address, 8009))
    print 'Connected!'
    if True:
        print 'Respawning netcat...'
        s.sendall('nohup nc -l -p 8009 -e /bin/sh &')
        time.sleep(0.5)
    if True:
        print 'Trying to start/restart kloned...'
        s.sendall('./startup/klone_start.sh')
        time.sleep(0.5)
        s.shutdown(socket.SHUT_WR)
    print 'Finished. Closing socket.'
    s.close()
except socket.error as e:
    print 'Unable to connect to %s.' % address