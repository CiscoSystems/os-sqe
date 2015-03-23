import paramiko
import re

client = paramiko.client.SSHClient()
client.load_system_host_keys()
client.connect('172.21.19.10', username='admin', password='Cisc0123')
stdin, stdout, stderr = client.exec_command(
    'scope security; '
    'show user-sessions local')
sessions = stdout.readlines()

session_names = list()
for session in sessions:
        s = re.split('\s+', session)
        if s[1] == 'admin' and 'web' in s[0]:
                session_names.append(s[0])

session_names.reverse()
for name in session_names:
        print 'Removing session %s' % name
        stdin, stdout, stderr = client.exec_command(
            'scope security; delete user-sessions local admin %s; '
            'commit-buffer' % name)
        print stdout.readlines()