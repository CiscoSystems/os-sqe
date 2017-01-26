class Wire(object):
    def __repr__(self):
        return u'{}:{}({}) -> {}:{} {}'.format(self._node_S.get_node_id(), self._port_S, self._mac or '',  self._node_N.get_node_id(), self._port_N, self._pc_id or '')

    def __init__(self, node_n, port_n, node_s, port_s, pc_id, mac):
        self._node_N = node_n
        self._port_N = port_n
        self._node_S = node_s
        self._port_S = port_s
        self._pc_id = pc_id
        self._mac = mac
        self._is_intentionally_down = False
        self._nics = set()  # list of NICs sitting on this wire, many to many relations

        self._pc_id = self._correct_pc_id(pc_id=pc_id)
        node_n.attach_wire(self)
        node_s.attach_wire(self)

    @staticmethod
    def add_wire(local_node, local_port_id, peer_desc):
        """Fabric to create a class Wire instance
        :param local_node: class LabNode instance
        :param local_port_id: string port id
        :param peer_desc: dictionary e.g. {peer-id: pxe,  peer-port: 1/20, own-mac: '70:e4:22:83:e6:52'}
        :returns class Wire instance
        """
        local_pid = local_node.correct_port_id(port_id=local_port_id)
        try:
            peer_node_id = peer_desc['peer-id']
            if peer_node_id.upper() == 'NONE':  # this port is not connected
                return None
            peer_port_id = peer_desc['peer-port']
        except KeyError as ex:
            raise ValueError('Node "{}": port "{}" has no "{}"'.format(local_node, local_pid, ex.message))
        try:
            peer_node = local_node.lab().get_node_by_id(peer_node_id)
        except ValueError:
            raise ValueError('Node "{}": specified wrong peer node id: "{}"'.format(local_node, peer_node_id))
        peer_port_id = peer_node.correct_port_id(port_id=peer_port_id, from_node=local_node)

        mac = local_node.calculate_mac(port_id=local_pid, mac=peer_desc.get('own-mac'))
        return Wire(node_n=peer_node, port_n=peer_port_id, node_s=local_node, port_s=local_pid, pc_id=peer_desc.get('port-channel'), mac=mac)

    def add_nic(self, nic):
        self._nics.add(nic)

    def get_nics(self):
        return self._nics

    def _correct_pc_id(self, pc_id):
        """This method is to make sure that port id gets a proper int value
        :param pc_id: correct values are port-channelXXX where XXX is a number or one of uplink and peerlink
        """

        if pc_id is None:  # this means that this wire does not participate in port channel
            return None
        elif pc_id == 'peerlink':
            if self.is_n9_n9():
                return 'port-channel100'
            else:
                raise ValueError('{}: peerlink should be between 2 N9'.format(self))
        elif pc_id == 'uplink':
            if self.is_n9_tor():
                return 'port-channel300'
            else:
                raise ValueError('{}: uplink should be between N9 and tor'.format(self))
        else:
            try:
                if not str(pc_id).startswith('port-channel'):
                    raise ValueError
                pc_id_int = int(pc_id.replace('port-channel', ''))  # tries to check int part
                if self.is_n9_fi() and pc_id_int >= 256:
                    raise ValueError('{}: pc id "{}" is not suitable for FI: int part must be less then 256'.format(self, pc_id))
                return pc_id
            except ValueError:
                raise ValueError('{}: port-channel must be port-channelXXX where XXX is int'.format(self))

    def down_port(self):
        """Delegate actual operation to north bound networking device"""
        self._is_intentionally_down = self._node_N.down_port(self)

    def is_port_intentionally_down(self):
        return self._is_intentionally_down

    def get_peer_node(self, node):
        return self._node_N if node == self._node_S else self._node_S

    def get_peer_port(self, node):
        return self._port_N if node == self._node_S else self._port_S

    def get_own_port(self, node):
        return self._port_N if node == self._node_N else self._port_S

    def get_node_s(self):
        return self._node_S

    def get_port_n(self):
        return self._port_N

    def get_port_s(self):
        return self._port_S

    def get_pc_id(self):
        return self._pc_id

    def is_n9_n9(self):
        from lab.nodes.n9k import Nexus

        return type(self._node_N) is Nexus and type(self._node_S) is Nexus

    def is_n9_tor(self):
        from lab.nodes.n9k import Nexus
        from lab.nodes.tor import Tor

        return type(self._node_N) is Tor and type(self._node_S) is Nexus

    def is_n9_oob(self):
        from lab.nodes.n9k import Nexus
        from lab.nodes.tor import Oob

        return type(self._node_N) is Oob and type(self._node_S) is Nexus

    def is_n9_pxe(self):
        from lab.nodes.n9k import Nexus
        from lab.nodes.tor import Pxe

        return type(self._node_N) is Pxe and type(self._node_S) is Nexus

    def is_n9_asr(self):
        from lab.nodes.n9k import Nexus
        from lab.nodes.asr import Asr

        return isinstance(self._node_S, Nexus) and isinstance(self._node_N, Asr)

    def is_n9_fi(self):
        from lab.nodes.n9k import Nexus
        from lab.nodes.fi import FI

        return isinstance(self._node_N, Nexus) and isinstance(self._node_S, FI)

    def is_n9_ucs(self):
        from lab.nodes.n9k import Nexus
        from lab.cimc import CimcServer

        return type(self._node_N) is Nexus and isinstance(self._node_S, CimcServer)

    def is_fi_ucs(self):
        from lab.nodes.fi import FI, FiServer

        return isinstance(self._node_N, FI) and isinstance(self._node_S, FiServer)

    def is_n9_cobbler(self):
        from lab.nodes.n9k import Nexus
        from lab.nodes.cobbler import CobblerServer

        return isinstance(self._node_N, Nexus) and isinstance(self._node_S, CobblerServer)

    def get_yaml_body(self):
        return '{:6}: {{peer-id: {:6}, peer-port: {:8} {:18} {:28}}}'.format(self._port_S, self._node_N.get_node_id(), self._port_N,
                                                                             '' if self._port_S == 'MGMT' else ', port-channel: pc{}'.format(self._pc_id),
                                                                             ', own-mac: {}'.format(self._mac.lower()) if self._port_S in ['LOM-1', 'LOM-2', 'MGMT'] and self._node_S.is_cimc_server() else '')

    def get_peer_link_yaml_body(self):
        return '{{own-id: {:8}, own-port: {:8}, peer-id: {:8}, peer-port: {:8}, port-channel: {:4}}}'.format(self._node_S.get_node_id(), self._port_S, self._node_N.get_node_id(), self._port_N, self._pc_id)

    def get_mac(self):
        return self._mac
