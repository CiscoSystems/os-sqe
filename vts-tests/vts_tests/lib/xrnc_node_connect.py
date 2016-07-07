import re

from vts_tests.lib import shell_connect


class XrncNodeConnect(shell_connect.ShellConnect):

    def interfaces_config(self):
        interfaces_text = self.run('cat /etc/network/interfaces')

        config = {}
        interface_name = ''
        for line in interfaces_text.split('\r\n'):
            sr = re.search('iface (?P<name>.*?) inet', line)
            if sr:
                interface_name = sr.group('name')
                config[interface_name] = ''
            if interface_name:
                config[interface_name] += line + '\r\n'
        return config