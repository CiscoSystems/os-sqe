import re

from vts_tests.lib import shell_connect


class XrvrNodeConnect(shell_connect.ShellConnect):

    def __init__(self, *args):
        super(XrvrNodeConnect, self).__init__(*args[0:-1])

        xrvr_info = args[-1]
        self._prompt_string = 'RP/0/0/CPU0:{hostname}#'.format(hostname=xrvr_info['hostname'].split('.', 1)[0])
        self.ssh_to(xrvr_info)
