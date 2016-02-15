class Wire(object):
    def __repr__(self):
        return u'S:{sn}:{sp} -> N:{nn}:{np} ({pc})'.format(sn=self.get_node_s().name(), sp=self.get_port_s(), nn=self.get_node_n().name(), np=self.get_port_n(), pc=self.get_pc_id())

    def __init__(self, node_n, num_n, node_s, num_s, pc_id=None):
        self._node_N = node_n  # always north bound networking device
        self._port_N = str(num_n)
        self._node_S = node_s
        self._port_S = str(num_s)
        self._pc_id = str(pc_id)  # not None if this wire is a part of (possibly virtual) port channel

        self._is_intentionally_down = False
        self._node_N.wire_downstream(self)
        self._node_S.wire_upstream(self)

    def down_port(self):
        """Delegate actual operation to north bound networking device"""
        self._is_intentionally_down = self._node_N.down_port(self)

    def is_port_intentionally_down(self):
        return self._is_intentionally_down

    def get_node_n(self):
        return self._node_N

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
