from lab.lab_node import LabNode


class Tor(LabNode):

    def cmd(self, cmd):
        return NotImplementedError


class Oob(LabNode):

    def cmd(self, cmd):
        return NotImplementedError
