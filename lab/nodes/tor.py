from lab.nodes import LabNode
from lab.nodes.n9k import Nexus


class Tor(Nexus):
    ROLE = 'tor'
    ROLE_OCTET = 'XX'


class Oob(Nexus):
    ROLE = 'oob'
    ROLE_OCTET = 'XX'

    def correct_port_id(self, port_id, from_node=None):
        err_msg = '{} {}: port id "{}" is wrong, it has to be <number>/<number>/<number>'.format('{} -> '.format(from_node) if from_node else '', self, port_id)
        i = 0
        for i, value in enumerate(port_id.split('/'), start=1):
            try:
                int(value)
            except ValueError:
                raise ValueError(err_msg)
        if i != 2:
            raise ValueError(err_msg)
        return 'Gig' + port_id


class Pxe(Nexus):
    ROLE = 'pxe'
    ROLE_OCTET = 'XX'


class Terminal(LabNode):
    ROLE = 'terminal'
    ROLE_OCTET = 'XX'

    def cmd(self, cmd):
        raise NotImplementedError
