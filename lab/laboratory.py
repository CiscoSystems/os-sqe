from lab.mercury.with_mercury import WithMercuryMixIn
from lab.ospd.with_osdp7 import WithOspd7
from lab.with_config import WithConfig
from lab.with_log import WithLogMixIn


class Laboratory(WithMercuryMixIn, WithOspd7, WithLogMixIn, WithConfig):
    TYPE_MERCURY_VTS = 'vts'
    TYPE_MERCURY_VPP = 'vpp'
    TYPE_RH_OSPD = 'ospd'
    SUPPORTED_TYPES = [TYPE_MERCURY_VTS, TYPE_MERCURY_VPP, TYPE_RH_OSPD]

    def __repr__(self):
        return self.name

    @staticmethod
    def sample_config():
        return 'path to lab config'

    def __init__(self, cfg_or_path):
        from lab import with_config
        from lab.nodes.virtual_server import VirtualServer
        from lab.network import Network
        from lab.nodes import LabNode
        from lab.wire import Wire

        if cfg_or_path is None:
            return
        elif type(cfg_or_path) is dict:
            self._cfg = cfg_or_path
        else:
            self._cfg = with_config.read_config_from_file(config_path=cfg_or_path)
        self.name = self._cfg['name']
        self.type = self._cfg['type']
        if self.type not in self.SUPPORTED_TYPES:
            raise ValueError('"{}" is not one of supported types: {}'.format(self.type, self.SUPPORTED_TYPES))

        self.setup_data = self._cfg.get('setup-data')
        self._unique_dict = dict()  # to make sure that all needed objects are unique

        self.dns, self.ntp = self._cfg['setup-data']['NETWORKING']['domain_name_servers'], self._cfg['setup-data']['NETWORKING']['ntp_servers']
        self.neutron_username, self.neutron_password = self._cfg['special-creds']['neutron_username'], self._cfg['special-creds']['neutron_password']

        self.networks = {net_desc['net-id']: Network.add_network(lab=self, net_id=net_desc['net-id'], net_desc=net_desc) for net_desc in self._cfg['networks']}

        self.nodes = LabNode.add_nodes(pod=self, nodes_cfg=self._cfg['switches'])  # first pass - just create nodes
        self.nodes.update(LabNode.add_nodes(pod=self, nodes_cfg=self._cfg['specials']))
        self.nodes.update(LabNode.add_nodes(pod=self, nodes_cfg=self._cfg['nodes']))
        if 'virtuals' in self._cfg:
            self.nodes.update(VirtualServer.add_nodes(pod=self, nodes_cfg=self._cfg['virtuals']))

        map(lambda n: self.make_sure_that_object_is_unique(obj=n.id, obj_type='node_id', owner=self), self.nodes.values())  # make sure that all nodes have unique ids

        if self._cfg['wires']:
            self.wires = Wire.add_wires(pod=self, wires_cfg=self._cfg['wires'])  # second pass - process wires to connect nodes to peers

        self._validate_config()

    def _validate_config(self):
        from lab.nodes.lab_server import LabServer

        map(lambda n: self.nodes[n['node']].add_nics(nics_cfg=n['nics']), self._cfg['nodes'] + self._cfg.get('virtuals', []))    # third pass - process all nics

        map(lambda n: self.make_sure_that_object_is_unique(obj=n.get_vlan_id(), obj_type='vlan', owner=n), self.networks.values())  # make sure that all nets have unique VLAN ID
        map(lambda n: self.make_sure_that_object_is_unique(obj=n.get_cidr(), obj_type='cidr', owner=n), self.networks.values())  # make sure that all nets have unique CIDR

        required_networks = {'a', 'm', 't', 's', 'e', 'p'}
        if set(self.networks.keys()) != required_networks:
            raise ValueError('{}: not all networks specified: "{}" is missing '.format(self, required_networks - set(self.networks.keys())))

        role_vs_nets = {}
        for net in self._cfg['networks']:
            for role in net['should-be']:
                role = role.lower()
                role_vs_nets.setdefault(role, set())
                role_vs_nets[role].add(net['net-id'])

        for node in self.nodes.values():
            if not isinstance(node, LabServer):
                continue
            actual_nets = set(node.get_nics().keys())
            req_nets = role_vs_nets[node.role]
            if actual_nets != req_nets:
                raise ValueError('{}: should be on nets {} while actually on {} (section nics)'.format(node, req_nets, actual_nets))
            # for nic in node.get_nics().values():
            #     self.make_sure_that_object_is_unique(obj=nic.get_ip_with_prefix(), node_id=node.get_node_id())
            #     for mac in nic.get_macs():
            #         self.make_sure_that_object_is_unique(obj=mac.lower(), node_id=node.get_node_id())  # check that all MAC are unique
            try:
                node.get_ssh_ip()
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

    def get_type(self):
        return self._lab_type

    def get_dns(self):
        return self._dns

    def get_ntp(self):
        return self._ntp

    def get_ansible_inventory(self):
        from lab.with_config import KEY_PRIVATE_PATH

        inventory = {}

        xrvr_username, xrvr_password = None, None
        xrvr_ips = []
        for node in self.xrvr:
            ip, xrvr_username, xrvr_password = node.get_xrvr_ip_user_pass()
            xrvr_ips.append(ip)

        for node in [self.mgmt] + self.vts:
            ip, username, _ = node.get_ssh()
            inventory[node.id] = {'hosts': [ip], 'vars': {'ansible_ssh_user': username, 'ansible_ssh_private_key_file': KEY_PRIVATE_PATH,
                                                          'xrvr_ip_mx': xrvr_ips, 'xrvr_username': xrvr_username, 'xrvr_password': xrvr_password}}

        for node in self.vim_tors:
            ip, username, password = node.get_oob()
            inventory[node.get_id()] = {'hosts': [ip], 'vars': {'ansible_ssh_user': username, 'ansible_ssh_pass': password}}

        return inventory

    def lab_validate(self):
        map(lambda x: x.r_verify_oob(), self.get_nodes_by_class())
        map(lambda x: x.n9_validate(), self.vim_tors + [self.vim_cat])

    def r_collect_information(self, regex, comment):
        import json

        version_dic = self.mgmt.r_get_version()
        body = json.dumps(version_dic) + '\n'
        for node in self.nodes.values():
            if hasattr(node, 'r_collect_logs'):
                body += node.r_collect_logs(regex=regex)
            if hasattr(node, 'r_collect_config'):
                body += node.r_collect_config()
        self.log_to_artifact(name=comment.replace(' ', '-') + '.txt', body=body)

    def exe(self, cmd):
        from lab.nodes.lab_server import LabServer

        return {node.get_id(): node.exe(cmd) for node in self.get_nodes_by_class(LabServer)}
