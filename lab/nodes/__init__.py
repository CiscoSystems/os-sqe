import abc

from lab.with_config import WithConfig
from lab.with_log import WithLogMixIn


class LabNode(WithLogMixIn, WithConfig):
    __metaclass__ = abc.ABCMeta

    _ROLE_VS_COUNT = {}

    def __init__(self, **kwargs):
        self._lab = kwargs.pop('lab')                     # link to parent Laboratory object
        self._id = kwargs['node-id'].strip()              # some id which unique in the given role, usually role + some small integer
        self._role = kwargs['role'].strip().lower()       # which role this node plays, possible roles are defined in get_role_class()
        self._proxy_node_id = kwargs['proxy-id']          # external ssh access via this node id or None
        if self._proxy_node_id is not None:
            self._proxy_node_id.strip()
        self.__proxy = None                               # instance of class LabNode ,will be used as proxy
        self._oob_ip, self._oob_username, self._oob_password = kwargs['oob-ip'], kwargs['oob-username'], kwargs['oob-password']
        self._ssh_username, self._ssh_password = kwargs['ssh-username'], kwargs['ssh-password']

        self._nics = dict()                  # list of NICs, will be filled in connect_node via class Wire
        self._ru, self._model = kwargs.get('ru', 'ruXX'), kwargs.get('model', 'XX')
        self._hostname = kwargs.get('hostname', 'XX')

        role = self._role.split('-')[0]      # e.g. control-fi and control-cimc are the same for counting
        self._ROLE_VS_COUNT.setdefault(role, 0)
        self._ROLE_VS_COUNT[role] += 1
        self._n = self._ROLE_VS_COUNT[role]  # number of this node in a list of nodes for this role
        self._wires = []

    def __repr__(self):
        return u'{} {}'.format(self.get_lab_id(), self.get_node_id())

    @property
    def _proxy(self):  # lazy initialisation, keep node id until the first use, then convert it to node reference
        if self.__proxy is None:
            try:
                self.__proxy = self._lab.get_node_by_id(self._proxy_node_id)
            except ValueError:
                self.__proxy = None
        return self.__proxy

    @staticmethod
    def add_node(lab, node_cfg):
        try:
            role = node_cfg['role']
            klass = LabNode.get_role_class(role)
            node_cfg['lab'] = lab
            return klass(**node_cfg)
        except KeyError as ex:
            raise ValueError('"{}"\nmust have parameter "{}"'.format(node_cfg['node-id'], ex))
        except TypeError as ex:
            raise TypeError('{} for the node "{}" of role "{}"'.format(ex, node_cfg.get('node-id'), node_cfg.get('role')))

    @staticmethod
    def add_nodes(lab, nodes_cfg):
        return [LabNode.add_node(lab=lab, node_cfg=node_cfg) for node_cfg in nodes_cfg]

    def get_proxy_node_id(self):
        return self._proxy_node_id

    def get_ssh_for_bash(self):
        return 'sshpass -p {} ssh {}@{}'.format(self._oob_password, self._oob_username, self._oob_ip)

    def get_ssh_u_p(self):
        return self._ssh_username, self._ssh_password

    def attach_wire(self, wire):
        self._wires.append(wire)

    def get_node_id(self):
        return self._id

    def get_lab_id(self):
        return str(self.lab())

    def get_role(self):
        return self._role

    def get_hostname(self):
        return self._hostname

    def get_model(self):
        return self._model

    def get_ru(self):
        return self._ru

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
        return self._wires

    def get_wires_to(self, node):
        """Returns wires to given node"""
        return filter(lambda x: x.get_peer_node(self) == node, self.get_all_wires())

    @abc.abstractmethod
    def cmd(self, cmd):
        pass  # this method allows to do OOB commands like e.g. CIMC or NXAPI

    def set_hardware_info(self, ru, model):
        self._ru, self._model = ru, model

    def get_hardware_info(self):
        return self._ru, self._model

    def is_cimc_server(self):
        from lab.nodes.cimc_server import CimcServer

        return isinstance(self, CimcServer)

    def is_fi_server(self):
        from lab.nodes.fi import FiServer

        return isinstance(self, FiServer)

    def is_director(self):
        from lab.nodes.fi import FiDirector
        from lab.nodes.cimc_server import CimcDirector

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
            mac = '{}0:{:02}:{}:{}:{:02}:CA'.format('1' if port_id == 'MLOM/1' else '0', self.lab().get_id(), o2, o3, self._n)
        return mac

    def r_verify_oob(self):
        import socket

        ip, _, _ = self.get_oob()
        if ip == 'MatchSSH':  # it's a virtual node no OOB
            return
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ok = None
        s.settimeout(2)
        try:
            s.connect((ip, 22))
            ok = 'ok'
        except (socket.timeout, socket.error):
            ok = 'FAILED'
        finally:
            self.log('OOB ({}) is {}'.format(ip, ok))
            s.close()

    @staticmethod
    def get_role_class(role):
        from lab.nodes.fi import FI, FiDirector, FiController, FiCompute, FiCeph
        from lab.nodes.n9k import Nexus, VimTor, VimCatalist
        from lab.nodes.asr import Asr
        from lab.nodes.tor import Tor, Oob, Pxe, Terminal
        from lab.nodes.cimc_server import CimcDirector, CimcController, CimcCompute, CimcCeph
        from lab.nodes.xrvr import Xrvr
        from lab.nodes.vtf import Vtf
        from lab.nodes.vtc import VtsHost
        from lab.nodes.vtc import Vtc

        role = role.lower()

        classes = [Tor, Oob, Pxe, Terminal, Nexus, VimTor, VimCatalist, CimcDirector, CimcController, CimcCompute, CimcCeph, VtsHost, Vtc, Vtf, Xrvr, Asr, FI, FiDirector, FiController, FiCompute, FiCeph]
        for klass in classes:
            if str(klass).split('.')[-1][:-2].lower() == role:
                return klass
        else:
            raise ValueError('role "{}" is not known. Possible roles: {}'.format(role, ' '.join(map(lambda x: str(x).split('.')[-1][:-2], classes))))
