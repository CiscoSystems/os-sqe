import datetime
import paramiko
import re
import sys


class ShellConnect(object):
    def __init__(self, *args):
        """
        :param args: List of servers info. Ex: {'ip': '10.30.117.6', 'hostname': 'build-node01', 'user': 'root', 'password': 'cisco123'}
        :return:
        """
        self._prompt_string = None
        if not args:
            raise Exception('Could not connect to nothing. Provide at least one server')
    
        self._jump_server = args[0]
        if not self._jump_server['ip'] or not self._jump_server['user'] \
            or not self._jump_server['password'] or not self._jump_server['hostname']:
            raise Exception('Invalid information {0}'.format(self._jump_server))
    
        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._ssh.connect(self._jump_server['ip'],
                          username=self._jump_server['user'],
                          password=self._jump_server['password'],
                          timeout=60)
        self._shell_channel = self._ssh.invoke_shell()
        self._shell_channel.settimeout(60)
        # server that we are working on right now
        self._server = self._jump_server

        # Receive login banner
        conn_time = datetime.datetime.now()
        prompt = self._make_prompt_string(self._server)
        buff = ''
        while prompt not in buff:
            resp = self._shell_channel.recv(1024)
            buff += resp
            if (datetime.datetime.now() - conn_time).seconds > 60:
                raise Exception('Could find prompt string "{0}" in the login banner {1}'.format(prompt, buff))

        if len(args) > 1:
            for srv in args[1:]:
                self.ssh_to(srv)
                # Successfully connected to another server so that change _server property
                self._server = srv
                # TODO: Need handle case when server asks for password

    def ssh_to(self, server):
        cmd = self._make_ssh_string(user=server['user'], ip=server['ip'])
        prompt = self._prompt_string or self._make_prompt_string(server)
        self._shell_channel.send(cmd + '\n')
        buff = ''
        while prompt not in buff:
            resp = self._shell_channel.recv(1024)
            buff += resp
            if re.search("'s password\:\s*$", buff):
                if 'password' not in server:
                    raise Exception('Server information does not contain password. '
                                    'The server ssh asks for password. '
                                    'Output: {output}. Server info: {si}'.format(output=buff, si=server))
                self._shell_channel.send(server['password'] + '\n')
                # Reset buffer -string
                buff = ''

    def run(self, cmd, expect=None, strip=True):
        expect = expect or self._prompt_string or self._make_prompt_string(self._server)
        sys.stdout.writelines('Call command: {0}'.format(cmd))
        self._shell_channel.send(cmd + '\n')
        buff = ''
        while expect not in buff:
            resp = self._shell_channel.recv(1024)
            buff += resp
        sys.stdout.writelines('Command output: ')
        sys.stdout.writelines(buff)
        return buff if not strip else re.sub('(\n|\r).*?$', '', re.sub('^.*?(\n|\r)', '', buff)).strip('\r\n')

    def _make_ssh_string(self, user, ip):
        return 'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {user}@{ip}'.format(user=user, ip=ip)

    def _make_prompt_string(self, server):
        return '{user}@{hostname}'.format(user=server['user'], hostname=server['hostname'].split('.', 1)[0])

    def ping(self, ip, count=4):
        output = self.run('ping -c {c} {ip}'.format(c=count, ip=ip))
        success_msg = '{c} packets transmitted, {c} received'.format(c=count)
        fail_msg = '{c} packets transmitted, 0 received, +{c} errors, 100% packet loss'.format(c=count)
        result = None
        if success_msg in output:
            result = True
        elif fail_msg in output:
            result = False
        return result
#
#
# if __name__ == '__main__':
#     srv1 = {'ip': '10.30.117.6', 'hostname': 'build-node01', 'user': 'root', 'password': 'cisco123'}
#     srv2 = {'ip': '10.123.123.21', 'hostname': 'i13-1-controller-3', 'user': 'root', 'password': 'cisco123'}
#
#     sc = ShellConnect(srv1, srv2)
#     ls = sc.run('ls')
#     pwd = sc.run('pwd')
#     ip_a = sc.run('ip a')
#     pass