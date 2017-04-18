from lab.nodes import LabNode
from lab.nodes.n9k import Nexus


class Tor(Nexus):
    ROLE = 'tor'
    ROLE_OCTET = 'XX'


class Oob(Nexus):
    ROLE = 'oob'
    ROLE_OCTET = 'XX'

    def correct_port_id(self, port_id, from_node=None):
        return port_id


class Pxe(Nexus):
    ROLE = 'pxe'
    ROLE_OCTET = 'XX'


class Terminal(LabNode):
    ROLE = 'terminal'
    ROLE_OCTET = 'XX'

    def cmd(self, cmd):
        raise NotImplementedError
