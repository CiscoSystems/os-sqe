from lab.with_log import WithLogMixIn
from lab.nodes.others import Tor, Oob, Pxe, VimTor, N9
from lab.nodes.fi import FI, FiServer
from lab.nodes.cimc_server import CimcServer
from lab.nodes.asr import Asr


class Wire(WithLogMixIn):
    def __repr__(self):
        return u'{}:{} {} -> {}:{} {}'.format(self.n1, self.port_id1, self.mac or '', self.n2, self.port_id2, self.pc_id or '')

    def __init__(self, node1, port_id1, mac,  node2, port_id2, pc_id):
        self.n1 = node1
        self.port_id1 = port_id1
        self.mac = mac
        self.n2 = node2
        self.port_id2 = port_id2

        self._is_intentionally_down = False
        self._nics = set()  # list of NICs sitting on this wire, many to many relations
        self.pc_id = pc_id
        self.log('created')

    @staticmethod
    def add_wire(pod, wire_cfg):
        """Fabric to create a class Wire instance
        :param pod: the instance of class Laboratory
        :param wire_cfg: a dicts like {node1: XXX, port1: XXX, mac1: XXX, node2 :XXX, port2: XXX mac2: XXX, pc-id: XXX}
        :returns class Wire instance
        """
        try:
            node_id1 = wire_cfg['node1']
            port_id1 = wire_cfg['port1']
            mac = wire_cfg['mac']
            node_id2 = wire_cfg['node2']
            port_id2 = wire_cfg['port2']
            pc_id = wire_cfg['pc-id']
        except KeyError as ex:
            raise ValueError('Wire "{}": has no "{}"'.format(wire_cfg, ex.message))
        try:
            node1 = pod.nodes[node_id1]
            node2 = pod.nodes.get(node_id2)
        except ValueError as ex:
            raise ValueError('wrong node id: "{}" on wire "{}"'.format(ex.message, wire_cfg))

        return Wire(node1=node1, port_id1=port_id1, mac=mac, node2=node2, port_id2=port_id2, pc_id=pc_id)

    @staticmethod
    def add_wires(pod, wires_cfg):
        return [Wire.add_wire(pod=pod, wire_cfg=wire_cfg) for wire_cfg in wires_cfg]

    def add_nic(self, nic):
        self._nics.add(nic)

    def get_nics(self):
        return self._nics

    def is_port_intentionally_down(self):
        return self._is_intentionally_down

    def get_peer_node(self, node):
        return self.n2 if node == self.n1 else self.n1

    def get_peer_port(self, node):
        return self.port_id2 if node == self.n1 else self.port_id1

    def get_own_port(self, node):
        return self.port_id1 if node == self.n1 else self.port_id2

    def _is_class_and_class(self, cls1, cls2):
        return isinstance(self.n1, cls1) and isinstance(self.n2, cls2)

    def is_n9_n9(self):
        return self._is_class_and_class(VimTor, VimTor)

    def is_n9_tor(self):
        return self._is_class_and_class(VimTor, Tor)

    def is_n9_oob(self):
        return self._is_class_and_class(VimTor, Oob)

    def is_n9_pxe(self):
        return self._is_class_and_class(VimTor, Pxe)

    def is_n9_asr(self):
        return self._is_class_and_class(VimTor, Asr)

    def is_n9_fi(self):
        return self._is_class_and_class(VimTor, FI)

    def is_n9_ucs(self):
        return self._is_class_and_class(N9, CimcServer)

    def is_fi_ucs(self):
        return self._is_class_and_class(FI, FiServer)
