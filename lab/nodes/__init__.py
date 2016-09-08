import abc

from lab.with_log import WithLogMixIn


class LabNode(WithLogMixIn):
    __metaclass__ = abc.ABCMeta

    _ROLE_VS_COUNT = {}

    def __init__(self, node_id, role, lab):
        self._lab = lab     # link to parent Laboratory object
        self._id = node_id  # some id which unique in the given role, usually role + some small integer
        self._role = role   # which role this node play, possible roles are defined in Laboratory
        role = role.split('-')[0]  # e.g. control-fi and control-cimc are the same for counting
        self._ROLE_VS_COUNT.setdefault(role, 0)
        self._ROLE_VS_COUNT[role] += 1
        self._n = self._ROLE_VS_COUNT[role]  # number of this node in a list of nodes for this role
        self._oob_ip, self._oob_username, self._oob_password = 'Default in LabNode.__init__()', 'Default in LabNode.__init__()', 'Default in LabNode.__init__()'
        self._nics = dict()  # list of NICs
        self._ru, self._model = 'Default in LabNod.__init()', 'Default in LabNod.__init()'

        self._upstream_wires = []
        self._downstream_wires = []
        self._peer_link_wires = []

    def wire_upstream(self, wire):
        self._upstream_wires.append(wire)

    def wire_downstream(self, wire):
        self._downstream_wires.append(wire)

    def wire_peer_link(self, wire):
        self._peer_link_wires.append(wire)

    def get_id(self):
        return self._id

    def get_role(self):
        return self._role

    def get_n_in_role(self):
        return self._n

    def lab(self):
        return self._lab

    def get_oob(self):
        return self._oob_ip, self._oob_username, self._oob_password

    def set_oob_creds(self, ip, username, password):
        self._oob_ip, self._oob_username, self._oob_password = ip, username, password

    def get_all_wires(self):
        """Returns all wires"""
        return self._downstream_wires + self._upstream_wires + self._peer_link_wires

    def get_wires_to(self, node):
        """Returns wires to given node"""
        return filter(lambda x: x.get_peer_node(self) == node, self.get_all_wires())

    def _assign_default_ip_index(self, net):
        chunk_size = (net.get_size() - 5) / 6  # bld/director, controls, computes, vts_hosts, vtc, xrvr, vtf

        if self.is_director():
            return 4
        elif self.is_controller():
            chunk = 0
        elif self.is_compute():
            chunk = 1
        elif self.is_ceph():
            chunk = 2
        elif self.is_vts_host():
            chunk = 3
        elif self.is_vtc():
            chunk = 4
        elif self.is_xrvr():
            chunk = 5
        elif self.is_vtf():
            chunk = 6
        else:
            raise ValueError('{} Can not detect the role of server'.format(self))
        return 4 + chunk * chunk_size + self._n

    def get_nic(self, nic):
        try:
            return self._nics[nic]
        except KeyError:
            return RuntimeError('{}: is not on {} network'.format(self.get_id(), nic))

    def get_nics(self):
        return self._nics

    @abc.abstractmethod
    def cmd(self, cmd):
        pass  # this method allows to do OOB commands like e.g. CIMC or NXAPI

    def form_mac(self, pattern):
        raise NotImplementedError('{}.form_mac() is not implemented'.format(type(self)))  # this method forms mac based on lab id node id and provided pattern

    def set_hardware_info(self, ru, model):
        self._ru, self._model = ru, model

    def get_hardware_info(self):
        return self._ru, self._model

    def is_cimc_server(self):
        from lab.cimc import CimcServer

        return isinstance(self, CimcServer)

    def is_fi_server(self):
        from lab.nodes.fi import FiServer

        return isinstance(self, FiServer)

    def is_director(self):
        from lab.nodes.fi import FiDirector
        from lab.cimc import CimcDirector

        return type(self) in [FiDirector, CimcDirector]

    def is_controller(self):
        from lab.nodes.fi import FiController
        from lab.cimc import CimcController

        return type(self) in [FiController, CimcController]

    def is_compute(self):
        from lab.nodes.fi import FiCompute
        from lab.cimc import CimcCompute

        return type(self) in [FiCompute, CimcCompute]

    def is_ceph(self):
        from lab.nodes.fi import FiCeph
        from lab.cimc import CimcCeph

        return type(self) in [FiCeph, CimcCeph]

    def is_vts_host(self):
        from lab.vts_classes.vtc import VtsHost

        return type(self) == VtsHost

    def is_vtc(self):
        from lab.vts_classes.vtc import Vtc

        return type(self) == Vtc

    def is_xrvr(self):
        from lab.vts_classes.xrvr import Xrvr

        return type(self) == Xrvr

    def is_vtf(self):
        from lab.vts_classes.vtf import Vtf

        return type(self) == Vtf
