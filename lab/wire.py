class Wire(object):
    def __repr__(self):
        return u'{}:{}({}) -> {}:{}({}) {}'.format(self._from['node'].get_node_id(), self._from['port-id'], self._from['mac'], self._to['node'].get_node_id(), self._to['port-id'], self._to['mac'], self._pc_id)

    def __init__(self, from_node, from_port_id, from_mac,  to_node, to_port_id, to_mac, pc_id):
        self._from = {'node': from_node, 'port-id': from_port_id, 'mac': from_mac}
        self._to = {'node': to_node, 'port-id': to_port_id, 'mac': to_mac}

        self._is_intentionally_down = False
        self._nics = set()  # list of NICs sitting on this wire, many to many relations
        self._pc_id = pc_id
        from_node.attach_wire(self)
        to_node.attach_wire(self)

    @staticmethod
    def add_wire(lab, wire_cfg):
        """Fabric to create a class Wire instance
        :param lab: the instance of class Laboratory
        :param wire_cfg: a dicts like {from-node-id: XXX, from-port-id: XXX, mac: XXX, to-node-id XXX, to-port-id: XXX mac: XXX, pc-id: XXX}
        :returns class Wire instance
        """
        try:
            from_node_id = wire_cfg['from-node-id'].strip()
            from_port_id = wire_cfg['from-port-id'].strip()
            from_mac = wire_cfg['from-mac'].strip()
            to_node_id = wire_cfg['to-node-id'].strip()
            if to_node_id == 'not_connected':
                return None
            to_port_id = wire_cfg['to-port-id'].strip()
            to_mac = wire_cfg['to-mac'].strip()
            pc_id = wire_cfg['pc-id'].strip()
        except KeyError as ex:
            raise ValueError('Wire "{}": has no "{}"'.format(wire_cfg, ex.message))
        try:
            from_node = lab.get_node_by_id(from_node_id)
            to_node = lab.get_node_by_id(to_node_id)
        except ValueError as ex:
            raise ValueError('wrong node id: "{}" on wire "{}"'.format(ex.message, wire_cfg))

        return Wire(from_node=from_node, from_port_id=from_port_id, from_mac=from_mac, to_node=to_node, to_port_id=to_port_id, to_mac=to_mac, pc_id=pc_id)

    @staticmethod
    def add_wires(lab, wires_cfg):
        return [Wire.add_wire(lab=lab, wire_cfg=wire_cfg) for wire_cfg in wires_cfg]

    def add_nic(self, nic):
        self._nics.add(nic)

    def get_nics(self):
        return self._nics

    def is_port_intentionally_down(self):
        return self._is_intentionally_down

    def get_peer_node(self, node):
        return self._to['node'] if node == self._from['node'] else self._from['node']

    def get_peer_port(self, node):
        return self._to['port-id'] if node == self._from else self._from['port-id']

    def get_own_port(self, node):
        return self._from['port-id'] if node == self._from else self._to['port-id']

    def get_pc_id(self):
        return self._pc_id

    def is_n9_n9(self):
        from lab.nodes.n9 import N9

        return type(self._from['node']) is N9 and type(self._to['node']) is N9

    def is_n9_tor(self):
        from lab.nodes.n9 import N9
        from lab.nodes.tor import Tor

        types = [type(self._from['node']), type(self._to['node'])]
        return N9 in types and Tor in types

    def is_n9_oob(self):
        from lab.nodes.n9 import N9
        from lab.nodes.tor import Oob

        types = [type(self._from), type(self._to)]
        return N9 in types and Oob in types

    def is_n9_pxe(self):
        from lab.nodes.n9 import N9
        from lab.nodes.tor import Pxe

        types = [type(self._from), type(self._to)]
        return N9 in types and Pxe in types

    def is_n9_asr(self):
        from lab.nodes.n9 import N9
        from lab.nodes.asr import Asr

        types = [type(self._from), type(self._to)]
        return N9 in types and Asr in types

    def is_n9_fi(self):
        from lab.nodes.n9 import N9
        from lab.nodes.fi import FI

        types = [type(self._from), type(self._to)]
        return N9 in types and FI in types

    def is_n9_ucs(self):
        from lab.nodes.n9 import N9
        from lab.nodes.cimc_server import CimcServer

        types = [type(self._from), type(self._to)]
        return N9 in types and CimcServer in types

    def is_fi_ucs(self):
        from lab.nodes.fi import FI, FiServer

        types = [type(self._from), type(self._to)]
        return FI in types and FiServer in types

    def is_n9_cobbler(self):
        from lab.nodes.n9 import N9
        from lab.nodes.cobbler import CobblerServer

        types = [type(self._from), type(self._to)]
        return N9 in types and CobblerServer in types

    def get_from_mac(self):
        return self._from['mac']

    def get_to_mac(self):
        return self._to['mac']
