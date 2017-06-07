from lab.nodes import LabNode
from lab.nodes.n9k import Nexus


class Tor(Nexus):
    def n9_show_running_config(self):
        return ''

class Oob(Nexus):
    def n9_show_running_config(self):
        return ''


class Pxe(Nexus):
    def n9_show_running_config(self):
        return ''


class Terminal(LabNode):
    ROLE_OCTET = 'XX'

    def cmd(self, cmd):
        raise NotImplementedError
