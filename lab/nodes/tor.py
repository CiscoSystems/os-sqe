from lab.nodes import LabNode
from lab.nodes.n9 import N9


class Tor(N9):
    pass


class Oob(N9):
    pass


class Pxe(N9):
    pass

class Terminal(LabNode):
    ROLE_OCTET = 'XX'

    def cmd(self, cmd):
        raise NotImplementedError
