from lab.nodes import LabNode
from lab.nodes.n9 import N9


class Tor(N9):
    def n9_show_running_config(self):
        return ''

class Oob(N9):
    def n9_show_running_config(self):
        return ''


class Pxe(N9):
    def n9_show_running_config(self):
        return ''


class Terminal(LabNode):
    ROLE_OCTET = 'XX'

    def cmd(self, cmd):
        raise NotImplementedError
