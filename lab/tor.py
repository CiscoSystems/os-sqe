from lab.lab_node import LabNode


class Tor(LabNode):

    def form_mac(self, pattern):
        raise NotImplementedError

    def cmd(self, cmd):
        raise NotImplementedError


class Oob(LabNode):

    def form_mac(self, pattern):
        raise NotImplementedError

    def cmd(self, cmd):
        raise NotImplementedError


class Pxe(LabNode):

    def form_mac(self, pattern):
        raise NotImplementedError

    def cmd(self, cmd):
        raise NotImplementedError
