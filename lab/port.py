class Port(object):

    def __init__(self, node, number):
        self.port_no = number
        self.node = node
        self.port_connected = None
        node.add_port(self)

    def connect_port(self, port):
        if self.port_connected:
            return
        self.port_connected = port
        port.connect_port(self)

    def is_port_connected(self):
        if self.port_connected:
            return True
        else:
            return False
