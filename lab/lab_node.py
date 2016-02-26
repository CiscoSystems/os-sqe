import abc


class LabNode(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, name, ip, username, password, lab, hostname):
        self._lab = lab  # link to parent Laboratory object
        self._name = name  # something which describes what this node is and how it will be used
        self._hostname = hostname  # usually it's actual hostname as reported by operation system of the node
        self._ip = ip
        self._username = username
        self._password = password
        self._upstream_wires = []
        self._downstream_wires = []

    def wire_upstream(self, wire):
        self._upstream_wires.append(wire)

    def wire_downstream(self, wire):
        self._downstream_wires.append(wire)

    def name(self):
        return self._name

    def index(self):
        """
        If name of a node is "node-3" the method returns 3.
        """
        return self.name().split('-')[-1]

    def lab(self):
        return self._lab

    def get_ssh(self):
        return self._ip, self._username, self._password, self._hostname

    def hostname(self):
        return self._hostname

    def get_pcs(self):
        """Returns all PC IDs found on all wires"""
        return set(map(lambda x: x.get_pc_id(), self._downstream_wires + self._upstream_wires))

    def get_all_wires(self):
        """Returns all ires"""
        return self._downstream_wires + self._upstream_wires

    @abc.abstractmethod
    def cmd(self, cmd):
        """
        :param cmd:
        :return:
        """
