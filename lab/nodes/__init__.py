import abc

from lab.with_config import WithConfig
from lab.with_log import WithLogMixIn


class LabNode(WithLogMixIn, WithConfig):
    __metaclass__ = abc.ABCMeta

    _ROLE_VS_COUNT = {}

    def __init__(self, pod, dic):
        self.pod = pod                                 # link to parent Laboratory object
        self.id = dic['id']                            # some id which unique in the given role, usually role + some small integer
        self.role = dic['role'].strip().lower()        # which role this node plays, possible roles are defined in get_role_class()
        self._proxy = dic.get('proxy')                 # LabNode object or node id (lazy init), will be used as proxy node to this node
        self.oob_ip, self.oob_username, self.oob_password = dic['oob-ip'], dic['oob-username'], dic['oob-password']
        self.ssh_username, self.ssh_password = dic.get('ssh-username', self.oob_username), dic.get('ssh-password', self.oob_password)

        role = self.role.split('-')[0]      # e.g. control-fi and control-cimc are the same for counting
        self._ROLE_VS_COUNT.setdefault(role, 0)
        self._ROLE_VS_COUNT[role] += 1
        self._n = self._ROLE_VS_COUNT[role]  # number of this node in a list of nodes for this role
        self._wires = []

    def __repr__(self):
        return self.id

    @property
    def proxy(self):  # lazy initialisation, node_id until the first use, then convert it to node reference
        if type(self._proxy) is str:
            self._proxy = self.pod.nodes[self._proxy] if self._proxy in self.pod.nodes else None
        return self._proxy

    @staticmethod
    def add_node(pod, node_cfg):
        try:
            role = node_cfg['role']
            klass = LabNode.get_role_class(role)
            return klass(pod=pod, dic=node_cfg)  # call class ctor
        except KeyError as ex:
            raise ValueError('Node "id: {}" must have key "{}"'.format(node_cfg.get('id', node_cfg), ex))

    @staticmethod
    def add_nodes(pod, nodes_cfg):
        return {x['id']: LabNode.add_node(pod=pod, node_cfg=x) for x in nodes_cfg}

    def get_ssh_for_bash(self):
        return 'sshpass -p {} ssh {}@{}'.format(self.oob_password, self.oob_username, self.oob_ip)

    def attach_wire(self, wire):
        self._wires.append(wire)

    def get_n_in_role(self):
        return self._n

    def get_all_wires(self):
        """Returns all wires"""
        return self._wires

    def get_wires_to(self, node):
        """Returns wires to given node"""
        return filter(lambda x: x.get_peer_node(self) == node, self.get_all_wires())

    @abc.abstractmethod
    def cmd(self, cmd):
        pass  # this method allows to do OOB commands like e.g. CIMC or NXAPI

    def is_cimc_server(self):
        from lab.nodes.cimc_server import CimcServer

        return isinstance(self, CimcServer)

    def is_fi_server(self):
        from lab.nodes.fi import FiServer

        return isinstance(self, FiServer)

    def is_director(self):
        from lab.nodes.fi import FiDirector
        from lab.nodes.mgmt_server import CimcDirector

        return type(self) in [FiDirector, CimcDirector]

    def is_controller(self):
        from lab.nodes.fi import FiController
        from lab.nodes.cimc_server import CimcController

        return type(self) in [FiController, CimcController]

    def is_compute(self):
        from lab.nodes.fi import FiCompute
        from lab.nodes.cimc_server import CimcCompute

        return type(self) in [FiCompute, CimcCompute]

    def is_ceph(self):
        from lab.nodes.fi import FiCeph
        from lab.nodes.cimc_server import CimcCeph

        return type(self) in [FiCeph, CimcCeph]

    def is_vts_host(self):
        from lab.nodes.vtc import VtsHost

        return type(self) == VtsHost

    def is_vtc(self):
        from lab.nodes.vtc import Vtc

        return type(self) == Vtc

    def is_xrvr(self):
        from lab.nodes.xrvr import Xrvr

        return type(self) == Xrvr

    def is_vtf(self):
        from lab.nodes.vtf import Vtf

        return type(self) == Vtf

    def is_virtual(self):
        return any([self.is_vtc(), self.is_xrvr(), self.is_vtf()])

    def calculate_mac(self, port_id, mac):
        import validators

        mac = str(mac)
        if not validators.mac_address(mac):
            if self.is_cimc_server():
                o2 = 'A0'  # UCS connected to N9
            elif self.is_fi_server():
                server_id = getattr(self, 'get_server_id')()  # UCS connected to FI
                o2 = 'B' + server_id.split('/')[-1] if '/' in server_id else 'C' + server_id
            else:
                o2 = 'E9'  # virtual machines

            if self.is_director():
                o3 = 'DD'
            elif self.is_controller():
                o3 = 'CC'
            elif self.is_compute():
                o3 = 'C0'
            elif self.is_ceph():
                o3 = 'CE'
            elif self.is_vtc():
                o3 = 'F0'
            elif self.is_xrvr():
                o3 = 'F1'
            elif self.is_vtf():
                o3 = 'F2'
            elif self.is_vts_host():
                o3 = 'F5'
            else:
                return None
            mac = '{}0:{:02}:{}:{}:{:02}:CA'.format('1' if port_id == 'MLOM/1' else '0', self.pod.get_id(), o2, o3, self._n)
        return mac

    def r_verify_oob(self):
        import socket

        if self.oob_ip == 'MatchSSH':  # it's a virtual node no OOB
            return
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ok = None
        s.settimeout(2)
        try:
            s.connect((self.oob_ip, 22))
            ok = 'ok'
        except (socket.timeout, socket.error):
            ok = 'FAILED'
        finally:
            self.log('OOB ({}) is {}'.format(self.oob_ip, ok))
            s.close()

    @staticmethod
    def get_role_class(role):
        from lab.nodes.fi import FI, FiDirector, FiController, FiCompute, FiCeph
        from lab.nodes.n9 import VimCat
        from lab.nodes.n9.vim_tor import VimTor
        from lab.nodes.n9 import N9
        from lab.nodes.asr import Asr
        from lab.nodes.tor import Tor, Oob, Pxe, Terminal
        from lab.nodes.cimc_server import CimcController, CimcCompute, CimcCeph
        from lab.nodes.mgmt_server import CimcDirector
        from lab.nodes.xrvr import Xrvr
        from lab.nodes.vtf import Vtf
        from lab.nodes.vtc import VtsHost
        from lab.nodes.vtc import Vtc

        role = role.lower()

        classes = [Tor, Oob, Pxe, Terminal, N9, VimTor, VimCat, CimcDirector, CimcController, CimcCompute, CimcCeph, VtsHost, Vtc, Vtf, Xrvr, Asr, FI, FiDirector, FiController, FiCompute, FiCeph]
        for klass in classes:
            if str(klass).split('.')[-1][:-2].lower() == role:
                return klass
        else:
            raise ValueError('role "{}" is not known. Possible roles: {}'.format(role, ' '.join(map(lambda x: str(x).split('.')[-1][:-2], classes))))
