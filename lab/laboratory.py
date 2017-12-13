from lab.mercury.with_mercury import WithMercury
from lab.ospd.with_osdp7 import WithOspd7
from lab.with_config import WithConfig
from lab.with_log import WithLogMixIn
from lab import decorators


class Laboratory(WithMercury, WithOspd7, WithLogMixIn, WithConfig):
    def __repr__(self):
        return self.name

    @staticmethod
    def sample_config():
        return 'path to lab config'

    def __init__(self, name='g72', release_tag='9.9.9', gerrit_tag=99, driver='vts', setup_data_dic=None):
        from lab.tims import Tims

        self._unique_dict = dict()  # to make sure that all needed objects are unique
        self.name = name + '-' + driver
        self.setup_data_dic = setup_data_dic
        self.driver = driver
        self.driver_version = None
        self.gerrit_tag = gerrit_tag
        self.release_tag = release_tag
        self.os_code_name = self.VIM_NUM_VS_OS_NAME_DIC[release_tag.rsplit('.', 1)[0]]
        self.dns = []
        self.ntp = []
        self.networks = {}
        self.tor = None
        self.oob = None
        self.vtc = None
        self.mgm = None
        self.vim_cat = None
        self.vim_tors = []
        self.controls = []
        self.computes = []
        self.cephs = []
        self.vts = []
        self.virtuals = []
        self.unknowns = []  # nodes detected to be connected to some switches, which is not a part of the lab
        self.wires = []
        self.is_sqe_user_created = False
        self.tims = Tims(version=self.version)

    @property
    def version(self):
        return '{}({}){}'.format(self.release_tag, self.gerrit_tag, self.driver.upper())

    @property
    def nodes_dic(self):
        return {x.id: x for x in [self.oob] + [self.tor] + [self.mgm] + [self.vtc] + self.controls + self.computes + self.cephs + self.vts + self.vim_tors + self.virtuals if x}

    @property
    def switches(self):
        return [x for x in [self.vim_cat] + self.vim_tors if x]

    @property
    def cimc_servers_dic(self):
        from lab.nodes.cimc_server import CimcServer

        return {x.id: x for x in [self.mgm] + self.controls + self.computes + self.cephs + self.vts if isinstance(x, CimcServer)}

    @staticmethod
    @decorators.section('Create pod from actual remote setup_data.xml')
    def create_from_remote(lab_name):
        return Laboratory.create(lab_name=lab_name)

    @staticmethod
    def create_from_config(cfg):
        from lab.network import Network
        from lab.nodes import LabNode
        from lab.wire import Wire

        pod = Laboratory()
        pod.name = cfg['name']

        pod.setup_data = cfg.get('setup-data')
        pod.dns.extend(pod.setup_data['NETWORKING']['domain_name_servers'])
        pod.ntp.extend(pod.setup_data['NETWORKING']['ntp_servers'])

        pod.networks.update(Network.add_networks(pod=pod, nets_cfg=cfg['networks']))

        tmp_nodes = []
        for sec in ['switches', 'specials', 'nodes', 'virtuals']:
            if sec in cfg:
                tmp_nodes.extend(LabNode.create_nodes(pod=pod, node_dics_lst=cfg[sec]))

        if cfg['wires']:
            pod.wires.extend(Wire.add_wires(pod=pod, wires_cfg=cfg['wires']))  # second pass - process wires to connect nodes to peers
        pod.validate_config()
        return pod

    def validate_config(self):
        from lab.nodes.lab_server import LabServer

        map(lambda n: self.make_sure_that_object_is_unique(obj=n.id, obj_type='node_id', owner=self), self.nodes_dic.values())  # make sure that all nodes have unique ids
        map(lambda n: self.make_sure_that_object_is_unique(obj=n.vlan, obj_type='vlan', owner=n), self.networks.values())  # make sure that all nets have unique VLAN ID
        map(lambda n: self.make_sure_that_object_is_unique(obj=n.net.cidr, obj_type='cidr', owner=n), self.networks.values())  # make sure that all nets have unique CIDR

        required_networks = {'a', 'm', 't', 's', 'e', 'p'}
        if set(self.networks.keys()) != required_networks:
            raise ValueError('{}: not all networks specified: "{}" is missing '.format(self, required_networks - set(self.networks.keys())))

        role_vs_nets = {}
        for net in self.networks.values():
            for role in net.roles_must_present:
                role_vs_nets.setdefault(role, set())
                role_vs_nets[role].add(net.id)

        for node in self.nodes_dic.values():
            if not isinstance(node, LabServer):
                continue
            actual_nets = set(node.nics.keys())
            req_nets = role_vs_nets[node.role]
            if actual_nets != req_nets:
                raise ValueError('{}: should be on nets {} while actually on {} (section nics)'.format(node, req_nets, actual_nets))
            # for nic in node.get_nics().values():
            #     self.make_sure_that_object_is_unique(obj=nic.get_ip_with_prefix(), node_id=node.get_node_id())
            #     for mac in nic.get_macs():
            #         self.make_sure_that_object_is_unique(obj=mac.lower(), node_id=node.get_node_id())  # check that all MAC are unique
            try:
                self.make_sure_that_object_is_unique(obj=node.ssh_ip, obj_type='ssh_ip', owner=node)
            except IndexError:
                raise ValueError('{}: no NIC is marked as is_ssh'.format(node))
            # for wire in node.get_all_wires():
            #     peer_node = wire.get_peer_node(node)
            #     peer_port_id = wire.get_peer_port(node)
            #     self.make_sure_that_object_is_unique(obj='{}-{}'.format(peer_node.get_node_id(), peer_port_id), owner=node.get_node_id())  # check that this peer_node-peer_port is unique

    def make_sure_that_object_is_unique(self, obj, obj_type, owner):
        """check that given object is unique
        :param obj: object which is supposed to be unique
        :param obj_type:  type of object like ip or vlan
        :param owner: other object which tries to own the object, usually node or lab
        """
        key = str(obj)
        if key == 'None':  # None is allowed to be owned by multiple objects
            return
        if key in self._unique_dict.keys():
            raise ValueError('{} tries to own {} {} which is already in use by {}'.format(owner, obj_type, key, self._unique_dict[key]))
        else:
            self._unique_dict[key] = owner

    def lab_validate(self):
        map(lambda x: x.r_verify_oob(), self.nodes_dic.values())
        map(lambda x: x.n9_validate(), self.vim_tors + [self.vim_cat])

    def r_collect_info(self, regex, comment):
        body = ''
        for node in self.computes + self.controls + self.cephs + ([self.vtc] if self.vtc else []):
            body += node.r_collect_info(regex=regex)
        self.log_to_artifact(name=comment.replace(' ', '-') + '.txt', body=body)

    def exe(self, cmd):
        from lab.nodes.lab_server import LabServer

        return {node.id: node.exe(cmd) for node in self.nodes_dic.values() if isinstance(node, LabServer)}

    def check_create_sqe_user(self):
        if not self.is_sqe_user_created:
            self.mgm.r_create_sqe_user()
            self.is_sqe_user_created = True
