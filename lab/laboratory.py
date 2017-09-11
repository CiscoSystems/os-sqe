from lab.mercury.with_mercury import WithMercuryMixIn
from lab.ospd.with_osdp7 import WithOspd7
from lab.with_config import WithConfig
from lab.with_log import WithLogMixIn
from lab import decorators


class Laboratory(WithMercuryMixIn, WithOspd7, WithLogMixIn, WithConfig):
    def __repr__(self):
        return self.name

    @staticmethod
    def sample_config():
        return 'path to lab config'

    def __init__(self):
        self._unique_dict = dict()  # to make sure that all needed objects are unique
        self.name = None
        self.setup_data = None
        self.driver = None
        self.driver_version = None
        self.gerrit_tag = None
        self.release_tag = None
        self.os_name = None
        self.namespace = None
        self.dns = []
        self.ntp = []
        self.networks = {}
        self.nodes = {}
        self.wires = []
        self.is_sqe_user_created = False

    @staticmethod
    @decorators.section('Create pod from actual remote setup_data.xml')
    def create_from_remote(lab_name):
        from tools.configurator_online import Configurator

        c = Configurator()
        return c.create(lab_name=lab_name)

    @staticmethod
    def create_from_path(cfg_path):
        cfg = Laboratory.read_config_from_file(config_path=cfg_path)
        return Laboratory.create_from_config(cfg=cfg)

    @staticmethod
    def create_from_config(cfg):
        from lab.nodes.virtual_server import VirtualServer
        from lab.network import Network
        from lab.nodes import LabNode
        from lab.wire import Wire

        pod = Laboratory()
        pod.name = cfg['name']

        pod.setup_data = cfg.get('setup-data')
        pod.dns.extend(pod.setup_data['NETWORKING']['domain_name_servers'])
        pod.ntp.extend(pod.setup_data['NETWORKING']['ntp_servers'])

        pod.networks.update(Network.add_networks(pod=pod, nets_cfg=cfg['networks']))

        pod.nodes.update(LabNode.create_nodes(pod=pod, node_dics_lst=cfg['switches']))  # first pass - just create nodes
        pod.nodes.update(LabNode.create_nodes(pod=pod, node_dics_lst=cfg['specials']))
        pod.nodes.update(LabNode.create_nodes(pod=pod, node_dics_lst=cfg['nodes']))
        if 'virtuals' in cfg:
            pod.nodes.update(VirtualServer.create_nodes(pod=pod, node_dics_lst=cfg['virtuals']))

        if cfg['wires']:
            pod.wires.extend(Wire.add_wires(pod=pod, wires_cfg=cfg['wires']))  # second pass - process wires to connect nodes to peers
        pod.validate_config()
        return pod

    def validate_config(self):
        from lab.nodes.lab_server import LabServer

        map(lambda n: self.make_sure_that_object_is_unique(obj=n.id, obj_type='node_id', owner=self), self.nodes.values())  # make sure that all nodes have unique ids
        map(lambda n: self.make_sure_that_object_is_unique(obj=n.vlan, obj_type='vlan', owner=n), self.networks.values())  # make sure that all nets have unique VLAN ID
        map(lambda n: self.make_sure_that_object_is_unique(obj=n.net.cidr, obj_type='cidr', owner=n), self.networks.values())  # make sure that all nets have unique CIDR

        required_networks = {'a', 'm', 't', 's', 'e', 'p'}
        if set(self.networks.keys()) != required_networks:
            raise ValueError('{}: not all networks specified: "{}" is missing '.format(self, required_networks - set(self.networks.keys())))

        role_vs_nets = {}
        for net in self.networks.values():
            for role in net.roles_must_present:
                role = role.lower()
                role_vs_nets.setdefault(role, set())
                role_vs_nets[role].add(net.id)

        for node in self.nodes.values():
            if not isinstance(node, LabServer):
                continue
            actual_nets = set(node.nics_dic.keys())
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

    @property
    def mgm(self):
        return filter(lambda x: x.is_mgm(), self.nodes.values())[0] or self.controls[0]  # if no specialized management node, use first control node

    @property
    def cobbler(self):
        return filter(lambda x: x.is_cobbler(), self.nodes.values())[0]

    @property
    def vim_tors(self):
        return filter(lambda x: x.is_vim_tor(), self.nodes.values())

    @property
    def vim_cat(self):
        return filter(lambda x: x.is_vim_cat(), self.nodes.values())

    @property
    def oob(self):
        return filter(lambda x: x.is_oob(), self.nodes.values())

    @property
    def tor(self):
        return filter(lambda x: x.is_tor(), self.nodes.values())

    @property
    def controls(self):
        return filter(lambda x: x.is_control(), self.nodes.values())

    @property
    def computes(self):
        return filter(lambda x: x.is_compute(), self.nodes.values())

    @property
    def vtc(self):
        return [x for x in self.nodes.values() if x.is_vtc()][0]

    @property
    def vts(self):
        return [x for x in self.nodes.values() if x.is_vts()]

    @property
    def cimc_servers(self):
        return filter(lambda x: x.is_cimc_server(), self.nodes.values())

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
        map(lambda x: x.r_verify_oob(), self.nodes.values())
        map(lambda x: x.n9_validate(), self.vim_tors + [self.vim_cat])

    def r_collect_info(self, regex, comment):
        body = ''
        for node in self.nodes.values():
            body += node.r_collect_info(regex=regex)
        self.log_to_artifact(name=comment.replace(' ', '-') + '.txt', body=body)

    def exe(self, cmd):
        from lab.nodes.lab_server import LabServer

        return {node.id: node.exe(cmd) for node in self.nodes.values() if isinstance(node, LabServer)}

    def check_create_sqe_user(self):
        if not self.is_sqe_user_created:
            self.mgm.r_create_sqe_user()
            self.is_sqe_user_created = True
