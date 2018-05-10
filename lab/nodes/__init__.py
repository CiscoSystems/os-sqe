import abc

from lab.with_log import WithLogMixIn


class LabNode(WithLogMixIn):
    __metaclass__ = abc.ABCMeta

    def __init__(self, pod, dic):
        self.pod = pod                                 # parent Laboratory object
        self.id = str(dic['id'])                       # some id which unique in the given role, usually role + some small integer
        self.role = dic['role'].strip()                # the role this node belongs
        self.short = self.short + self.id[-1]          # short single letter and digit name used in TOR descr
        self._proxy = dic.get('proxy')                 # LabNode object or node id (lazy init), will be used as proxy node to this node
        self.oob_ip, self.oob_username, self.oob_password = dic['oob-ip'], dic['oob-username'], dic['oob-password']
        self.hardware = ''                             # some hardware related info which might be useful for debugging

    def __repr__(self):
        return self.id + '@' + self.pod.name

    @property
    def proxy(self):  # lazy initialisation, node_id until the first use, then convert it to node object
        if type(self._proxy) is str:
            self._proxy = self.pod.nodes[self._proxy] if self._proxy in self.pod.nodes else None
        return self._proxy

    @staticmethod
    def create_node(pod, dic):
        """Fabric to create a LabNode() or derived
        :param pod: lab.laboratory.Laboratory()
        :param dic: {'id': , 'role': , 'proxy': , 'oob-ip':, 'oob-username': , 'oob-password':, 'ssh-username':, 'ssh-password':, 'nics': [check in lab.network.Nic]}
        :return:
        """
        try:
            role_class_name = dic['role']
            klass = pod.ROLE_ID_TO_CLASS_DIC[role_class_name]
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
        return [LabNode.create_node(pod=pod, dic=x) for x in node_dics_lst]

    @abc.abstractmethod
    def cmd(self, cmd):
        pass  # this method allows to do OOB commands like e.g. CIMC or NXAPI


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

        if not self.oob_ip:  # it's a virtual node no OOB
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
            self.log('OOB={:15} status={}'.format(self.oob_ip, ok))
            s.close()
