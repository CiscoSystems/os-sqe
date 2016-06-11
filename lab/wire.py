class Wire(object):
    def __repr__(self):
        return u'S:{sn}:{sp} -> N:{nn}:{np} ({pc}) on vlans: {vlan}'.format(sn=self.get_node_s().get_id(), sp=self.get_port_s(), nn=self.get_node_n().get_id(), np=self.get_port_n(), pc=self.get_pc_id(), vlan=self._vlans)

    def __init__(self, node_n, port_n, node_s, port_s, port_channel, vlans):
        self._node_N = node_n
        self._port_N = str(port_n)
        self._node_S = node_s
        self._port_S = str(port_s)
        self._pc_id = self._calculate_pc_id(port_channel)
        self._is_peer_link = self.is_n9_n9()
        self._vlans = vlans  # single wire may have many vlans

        self._is_intentionally_down = False

        if self._is_peer_link:
            self._node_N.wire_peer_link(self)
            self._node_S.wire_peer_link(self)
        else:
            self._node_N.wire_downstream(self)
            self._node_S.wire_upstream(self)

    def _calculate_pc_id(self, pc_id):
        """S
        :param pc_id:
        """
        import re

        if pc_id is None:
            return None

        try:
            return int(re.findall('^(\d+)', pc_id)[0])
        except IndexError:
            if self.is_n9_tor():
                pc_id = 300
            elif self.is_n9_n9():
                pc_id = 100
            elif self.is_n9_fi():
                pc_id = self._node_S.node_index()
                if pc_id >= 256:
                    raise ValueError('Node {0} has index which is not suitable for (v)PC- more then 256'.format(self._node_S))
            else:
                pc_id = pc_id  # other connection types do not require (v)PC
            return pc_id

    def down_port(self):
        """Delegate actual operation to north bound networking device"""
        self._is_intentionally_down = self._node_N.down_port(self)

    def is_port_intentionally_down(self):
        return self._is_intentionally_down

    def get_node_n(self):
        return self._node_N

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
        from lab.n9k import Nexus

        return isinstance(self._node_N, Nexus) and isinstance(self._node_S, Nexus)

    def is_n9_tor(self):
        from lab.n9k import Nexus
        from lab.tor import Tor

        return isinstance(self._node_N, Tor) and isinstance(self._node_S, Nexus)

    def is_n9_asr(self):
        from lab.n9k import Nexus
        from lab.asr import Asr

        return isinstance(self._node_S, Nexus) and isinstance(self._node_N, Asr)

    def is_n9_fi(self):
        from lab.n9k import Nexus
        from lab.fi import FI

        return isinstance(self._node_N, Nexus) and isinstance(self._node_S, FI)

    def is_n9_ucs(self):
        from lab.n9k import Nexus
        from lab.cimc import CimcServer

        return isinstance(self._node_N, Nexus) and isinstance(self._node_S, CimcServer)

    def is_fi_ucs(self):
        from lab.fi import FI, FiServer

        return isinstance(self._node_N, FI) and isinstance(self._node_S, FiServer)

    def is_n9_cobbler(self):
        from lab.n9k import Nexus
        from lab.cobbler import CobblerServer

        return isinstance(self._node_N, Nexus) and isinstance(self._node_S, CobblerServer)

    def get_vlans(self):
        return self._vlans
