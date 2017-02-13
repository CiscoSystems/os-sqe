from lab.nodes.lab_server import LabServer


class VirtualServer(LabServer):
    def __init__(self, **kwargs):
        super(VirtualServer, self).__init__(**kwargs)
        self._hard_server = self.lab().get_node_by_id(kwargs['virtual-on'])
        self._hard_server.add_virtual_server(self)

    def cmd(self, cmd):
        raise NotImplementedError()

    def get_hardware_server(self):
        return self._hard_server

    def correct_port_id(self, port_id, from_node=None):
        return port_id
