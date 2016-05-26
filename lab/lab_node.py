import abc


class LabNode(object):
    __metaclass__ = abc.ABCMeta

    def __repr__(self):
        return u'{l} {n} | sshpass -p {p} ssh {u}@{ip}'.format(l=self.lab(), n=self.name(), p=self._password, u=self._username, ip=self._ip)

    def __init__(self, name, role, ip, username, password, lab, hostname):
        self._lab = lab  # link to parent Laboratory object
        self._name = name  # something which describes what this node
        self._role = role  # which roles this node play
        self._hostname = hostname  # usually it's actual hostname as reported by operation system of the node
        self._ip = ip
        self._username = username
        self._password = password
        self._upstream_wires = []
        self._downstream_wires = []
        self._peer_link_wires = []

    def wire_upstream(self, wire):
        self._upstream_wires.append(wire)

    def wire_downstream(self, wire):
        self._downstream_wires.append(wire)

    def wire_peer_link(self, wire):
        self._peer_link_wires.append(wire)

    def name(self):
        return self._name

    def role(self):
        return self._role

    def node_index(self):
        """ If name of a node is "node-3" the method returns 3 """
        try:
            return int(self.name().split('-')[-1])
        except ValueError:
            raise ValueError('Node "{0}" is not of form role-integer'.format(self._name))

    def lab(self):
        return self._lab

    def get_ssh(self):
        return self._ip, self._username, self._password, self._hostname

    def hostname(self):
        return self._hostname

    def get_all_wires(self):
        """Returns all ires"""
        return self._downstream_wires + self._upstream_wires

    @abc.abstractmethod
    def cmd(self, cmd):
        """
        :param cmd:
        :return:
        """
