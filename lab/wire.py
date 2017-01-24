class Wire(object):
    def __repr__(self):
        return u'{}-{}({}) -> {}:{} pc{}'.format(self._node_S.get_id(), self._port_S, self._mac,  self._node_N.get_id(), self._port_N, self.get_pc_id())

    def __init__(self, node_n, port_n, node_s, port_s, pc_id, mac):
        self._node_N = node_n
        self._port_N = port_n
        self._node_S = node_s
        self._port_S = port_s
        self._pc_id = self._correct_pc_id(pc_id=pc_id)
        self._is_peer_link = self.is_n9_n9()
        self._mac = mac

        self._is_intentionally_down = False

        if self._is_peer_link:
            self._node_N.wire_peer_link(self)
            self._node_S.wire_peer_link(self)
        else:
            self._node_N.wire_downstream(self)
            self._node_S.wire_upstream(self)

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
            peer_port_id = peer_desc['peer-port']
        except KeyError as ex:
            raise ValueError('Node "{}": port "{}" has no "{}"'.format(local_node, local_pid, ex.message))
        try:
            peer_node = local_node.lab().get_node_by_id(peer_node_id)
        except ValueError:
            raise ValueError('Node "{}": specified wrong peer node id: "{}"'.format(local_node, peer_node_id))
        peer_port_id = peer_node.correct_port_id(port_id=peer_port_id)

        mac = local_node.calculate_mac(port_id=local_pid, mac=peer_desc.get('own-mac'))
        return Wire(node_n=peer_node, port_n=peer_port_id, node_s=local_node, port_s=local_pid, pc_id=peer_desc.get('port-channel'), mac=mac)

    def _correct_pc_id(self, pc_id):
        """This method is to make sure that port id gets a proper int value
        :param pc_id: correct values are pcXXX where XXX is a number
        """
        import re

        if pc_id is None:  # this means that this wire does not participate in port channel
            return None

        try:
            pc_id = int(re.findall('(\d+)', str(pc_id))[0])  # tries to find int - if ok then use it
            if self.is_n9_fi() and pc_id >= 256:
                raise ValueError('Node {}: has port-channel id {} is not suitable for FI (v)PC- more then 256'.format(self._node_S, pc_id))
            return pc_id
        except IndexError:
            if self.is_n9_tor():
                pc_id = 300
            elif self.is_n9_n9():
                pc_id = 100
            elif self.is_n9_fi():
                pc_id = 250
            elif self.is_n9_ucs():  # we assign port id as port-channel id
                pc_id = self._port_N.split('/')[1]
            return pc_id

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

    def get_vlans(self):
        return self._vlans

    def get_yaml_body(self):
        return '{:6}: {{peer-id: {:6}, peer-port: {:8} {:18} {:28}}}'.format(self._port_S, self._node_N.get_node_id(), self._port_N,
                                                                             '' if self._port_S == 'MGMT' else ', port-channel: pc{}'.format(self._pc_id),
                                                                             ', own-mac: {}'.format(self._mac.lower()) if self._port_S in ['LOM-1', 'LOM-2', 'MGMT'] and self._node_S.is_cimc_server() else '')

    def get_peer_link_yaml_body(self):
        return '{{own-id: {:8}, own-port: {:8}, peer-id: {:8}, peer-port: {:8}, port-channel: {:4}}}'.format(self._node_S.get_node_id(), self._port_S, self._node_N.get_node_id(), self._port_N, self._pc_id)

    def get_mac(self):
        return self._mac
