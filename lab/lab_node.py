import abc


class LabNode(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, ip, username, password, lab, ports=None):
        self.ip = ip
        self.username = username
        self.password = password
        self.lab = lab
        self.ports = ports or []

    def add_port(self, port):
        self.ports.append(port)

    @abc.abstractmethod
    def cmd(self, cmd):
        """
        :param cmd:
        :return:
        """
