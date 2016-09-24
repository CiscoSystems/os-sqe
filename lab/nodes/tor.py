from lab.nodes import LabNode


class Tor(LabNode):
    ROLE = 'tor'
    ROLE_OCTET = 'XX'

    def cmd(self, cmd):
        raise NotImplementedError


class Oob(LabNode):
    ROLE = 'oob'
    ROLE_OCTET = 'XX'

    def cmd(self, cmd):
        raise NotImplementedError


class Pxe(LabNode):
    ROLE = 'pxe'
    ROLE_OCTET = 'XX'

    def cmd(self, cmd):
        raise NotImplementedError


class Terminal(LabNode):
    ROLE = 'terminal'
    ROLE_OCTET = 'XX'

    def cmd(self, cmd):
        raise NotImplementedError
