from lab.nodes import LabNode
from lab.nodes.n9k import Nexus


class Tor(Nexus):
    ROLE_OCTET = 'XX'


class Oob(Nexus):
    ROLE_OCTET = 'XX'


class Pxe(Nexus):
    ROLE_OCTET = 'XX'


class Terminal(LabNode):
    ROLE_OCTET = 'XX'

    def cmd(self, cmd):
        raise NotImplementedError
