from lab.mercury.with_mercury import WithMercuryMixIn
from lab.ospd.with_osdp7 import WithOspd7
from lab.with_config import WithConfig
from lab.with_log import WithLogMixIn
from lab import decorators


class Laboratory(WithMercuryMixIn, WithOspd7, WithLogMixIn, WithConfig):
    TYPE_MERCURY_VTS = 'vts'
    TYPE_MERCURY_VPP = 'vpp'
    TYPE_RH_OSPD = 'ospd'
    SUPPORTED_TYPES = [TYPE_MERCURY_VTS, TYPE_MERCURY_VPP, TYPE_RH_OSPD]

    def __repr__(self):
        return self.name + '-' + self.driver

    @staticmethod
    def sample_config():
        return 'path to lab config'

    def __init__(self):
        self._unique_dict = dict()  # to make sure that all needed objects are unique
        self.name = None
        self.setup_data = None
        self.dns = []
        self.ntp = []
        self.networks = {}
        self.nodes = {}
        self.wires = []

    @staticmethod
    @decorators.section('Create config from remote setup_data.xml')
    def create_from_remote(ip):
        from tools.configurator import Configurator

        c = Configurator()
        return c.create_from_remote(ip=ip)

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

        pod.nodes.update(LabNode.add_nodes(pod=pod, nodes_cfg=cfg['switches']))  # first pass - just create nodes
        pod.nodes.update(LabNode.add_nodes(pod=pod, nodes_cfg=cfg['specials']))
        pod.nodes.update(LabNode.add_nodes(pod=pod, nodes_cfg=cfg['nodes']))
        if 'virtuals' in cfg:
            pod.nodes.update(VirtualServer.add_nodes(pod=pod, nodes_cfg=cfg['virtuals']))

        if cfg['wires']:
            pod.wires.extend(Wire.add_wires(pod=pod, wires_cfg=cfg['wires']))  # second pass - process wires to connect nodes to peers
        pod.validate_config()
        return pod

    @staticmethod
    def create_from_path(cfg_path):
        cfg = Laboratory.read_config_from_file(config_path=cfg_path)
        return Laboratory.create_from_config(cfg=cfg)

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

    def get_nodes_by_class(self, klass=None):
        if klass:
            classes = klass if type(klass) is list else [klass]
            nodes = []
            for klass in classes:
                nodes += filter(lambda x: isinstance(x, klass), self.nodes.values())
            return nodes
        else:
            return self.nodes.values()

    @property
    def driver(self):
        return self.setup_data['MECHANISM_DRIVERS']

    @property
    def mgmt(self):
        from lab.nodes.mgmt_server import CimcDirector
        from lab.nodes.fi import FiDirector

        return filter(lambda x: type(x) in [CimcDirector, FiDirector], self.nodes.values())[0] or self.controls[0]  # if no specialized managment node, use first control node

    @property
    def cobbler(self):
        from lab.nodes.cobbler import CobblerServer

        return filter(lambda x: type(x) in [CobblerServer], self.nodes.values())[0]

    @property
    def vim_tors(self):
        from lab.nodes.n9.vim_tor import VimTor

        return filter(lambda x: type(x) is VimTor, self.nodes.values())

    @property
    def vim_cat(self):
        from lab.nodes.n9 import VimCat

        return filter(lambda x: type(x) is VimCat, self.nodes.values())

    @property
    def oob(self):
        from lab.nodes.tor import Oob

        return filter(lambda x: type(x) is Oob, self.nodes.values())

    @property
    def tor(self):
        from lab.nodes.tor import Tor

        return filter(lambda x: type(x) is Tor, self.nodes.values())

    @property
    def controls(self):
        from lab.nodes.cimc_server import CimcController
        from lab.nodes.fi import FiController

        return filter(lambda x: type(x) in [CimcController, FiController], self.nodes.values())

    @property
    def computes(self):
        from lab.nodes.cimc_server import CimcCompute
        from lab.nodes.fi import FiCompute

        return filter(lambda x: type(x) in [CimcCompute, FiCompute], self.nodes.values())

    @property
    def vtc(self):
        from lab.nodes.vtc import Vtc

        return filter(lambda x: type(x) is Vtc, self.nodes.values())


    @property
    def cimc_servers(self):
        from lab.nodes.cimc_server import CimcServer

        return self.get_nodes_by_class(klass=CimcServer)

    def get_ucsm_nets_with_pxe(self):
        return [x for x in self._cfg['nets'].keys() if 'pxe' in x]

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

    def get_ansible_inventory(self):
        inventory = {}

        xrvr_username, xrvr_password = None, None
        xrvr_ips = []
        for node in self.xrvr:
            ip, xrvr_username, xrvr_password = node.get_xrvr_ip_user_pass()
            xrvr_ips.append(ip)

        for node in [self.mgmt] + self.vts:
            ip, username, _ = node.get_ssh()
            inventory[node.id] = {'hosts': [ip], 'vars': {'ansible_ssh_user': username, 'ansible_ssh_private_key_file': self.KEY_PRIVATE_PATH,
                                                          'xrvr_ip_mx': xrvr_ips, 'xrvr_username': xrvr_username, 'xrvr_password': xrvr_password}}

        for node in self.vim_tors:
            ip, username, password = node.get_oob()
            inventory[node.get_id()] = {'hosts': [ip], 'vars': {'ansible_ssh_user': username, 'ansible_ssh_pass': password}}

        return inventory

    def lab_validate(self):
        map(lambda x: x.r_verify_oob(), self.get_nodes_by_class())
        map(lambda x: x.n9_validate(), self.vim_tors + [self.vim_cat])

    def r_collect_information(self, regex, comment):
        body = ''
        for node in self.nodes.values():
            if hasattr(node, 'r_collect_logs'):
                body += node.r_collect_logs(regex=regex)
            if hasattr(node, 'r_collect_config'):
                body += node.r_collect_config()
        self.log_to_artifact(name=comment.replace(' ', '-') + '.txt', body=body)

    def exe(self, cmd):
        from lab.nodes.lab_server import LabServer

        return {node.get_id(): node.exe(cmd) for node in self.get_nodes_by_class(LabServer)}
