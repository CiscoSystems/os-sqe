import abc

from lab.with_config import WithConfig
from lab.with_log import WithLogMixIn


class LabNode(WithLogMixIn, WithConfig):
    __metaclass__ = abc.ABCMeta

    def __init__(self, pod, dic):
        self.pod = pod                                 # link to parent Laboratory object
        self.id = str(dic['id'])                       # some id which unique in the given role, usually role + some small integer
        self.role = dic['role'].strip()                # which role this node plays, possible roles are defined in get_role_class()
        self._proxy = dic.get('proxy')                 # LabNode object or node id (lazy init), will be used as proxy node to this node
        self.oob_ip, self.oob_username, self.oob_password = dic['oob-ip'], dic['oob-username'], dic['oob-password']
        self.hardware = ''                             # some description which might be useful for debugging
        self.log('created')

    def __repr__(self):
        return self.id

    @property
    def proxy(self):  # lazy initialisation, node_id until the first use, then convert it to node reference
        if type(self._proxy) is str:
            self._proxy = self.pod.nodes[self._proxy] if self._proxy in self.pod.nodes else None
        return self._proxy

    @staticmethod
    def create_node(pod, dic):
        """Fabric to create a LabServer() or derived

        :param pod: lab.laboratory.Laboratory()
        :param dic: {'id': , 'role': , 'proxy': , 'oob-ip':, 'oob-username': , 'oob-password':, 'ssh-username':, 'ssh-password':, 'nics': [check in lab.network.Nic]}
        :return:
        """
        try:
            role = dic['role']
            klass = LabNode.get_role_class(role)
            return klass(pod=pod, dic=dic)  # call class ctor
        except KeyError as ex:
            raise ValueError('Node "id: {}" must have key "{}"'.format(dic.get('id', dic), ex))

    @staticmethod
    def create_nodes(pod, node_dics_lst):
        """Fabric to create a number of nodes
        :param pod: lab.laboratory.Laboratory()
        :param node_dics_lst: list of dicts
        :return: list of objects inhereting from LabNode class
        """
        return {x['id']: LabNode.create_node(pod=pod, dic=x) for x in node_dics_lst}

    @abc.abstractmethod
    def cmd(self, cmd):
        pass  # this method allows to do OOB commands like e.g. CIMC or NXAPI

    def is_oob(self):
        from lab.nodes.others import Oob

        return type(self) is Oob

    def is_tor(self):
        from lab.nodes.others import Tor

        return type(self) is Tor

    def is_vim_tor(self):
        from lab.nodes.others import VimTor

        return type(self) is VimTor

    def is_vim_cat(self):
        from lab.nodes.others import VimCat

        return type(self) is VimCat

    def is_cimc_server(self):
        from lab.nodes.cimc_server import CimcServer

        return isinstance(self, CimcServer)

    def is_fi_server(self):
        from lab.nodes.fi import FiServer

        return isinstance(self, FiServer)

    def is_mgm(self):
        from lab.nodes.fi import FiDirector
        from lab.nodes.mgmt_server import CimcDirector

        return type(self) in [FiDirector, CimcDirector]

    def is_control(self):
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

    def is_vts(self):
        from lab.nodes.cimc_server import CimcVts

        return type(self) == CimcVts

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
        from lab.nodes.virtual_server import VirtualServer

        return isinstance(self, VirtualServer)

    def is_vip(self):
        from lab.nodes.virtual_server import VipServer

        return isinstance(self, VipServer)

    # def calculate_mac(self, port_id, mac):
    #     o3 = {'CimcDirector': 'DD', 'CimcController': 'CC', 'CimcCompute': 'C0', 'CimcCeph': 'CE', 'Vtc': 'F0', 'Xrvr': 'F1', 'Vtf': 'F2', 'Vts': 'F5'}[self.__class__.__name__]
    #     o2 = 'A0' if self.is_cimc_server() else 'E9'  # UCS connected to N9 or Virtual server
    #     if self.is_fi_server():
    #         server_id = getattr(self, 'get_server_id')()  # UCS connected to FI
    #         o2 = 'B' + server_id.split('/')[-1] if '/' in server_id else 'C' + server_id
    #
    #     return mac or '{}0:{:02}:{}:{}:{:02}:CA'.format('1' if port_id == 'MLOM/1' else '0', self.pod.get_id(), o2, o3, self._n)

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
        from lab.nodes.n9 import N9
        from lab.nodes.asr import Asr
        from lab.nodes.others import Tor, Oob, Pxe, Terminal, VimCat, VimTor, UnknownN9
        from lab.nodes.cimc_server import CimcController, CimcCompute, CimcCeph, CimcVts
        from lab.nodes.mgmt_server import CimcDirector
        from lab.nodes.xrvr import Xrvr
        from lab.nodes.vtf import Vtf
        from lab.nodes.vtc import Vtc
        from lab.nodes.vtsr import Vtsr
        from lab.nodes.virtual_server import VtcIndividual, VtsrIndividual

        classes = {x.__name__: x for x in [Tor, Oob, Pxe, Terminal, N9, UnknownN9,
                                           VimTor, VimCat, CimcDirector, CimcController, CimcCompute, CimcCeph, CimcVts,
                                           Vtc, VtcIndividual, Vtf, Xrvr, VtsrIndividual, Asr,
                                           FI, FiDirector, FiController, FiCompute, FiCeph]}
        try:
            return classes[role]
        except KeyError:
            raise ValueError('role "{}" is not known. Possible roles: {}'.format(role, classes.keys()))

    def r_collect_info(self, regex):
        return ''
