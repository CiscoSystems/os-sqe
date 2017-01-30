from lab.mercury.with_mercury import WithMercuryMixIn
from lab.ospd.with_osdp7 import WithOspd7
from lab.with_config import WithConfig
from lab.with_log import WithLogMixIn


class Laboratory(WithMercuryMixIn, WithOspd7, WithLogMixIn, WithConfig):
    def __repr__(self):
        return self._lab_name

    @staticmethod
    def sample_config():
        return 'path to lab config'

    def __init__(self, config_path):
        from lab import with_config
        from lab.network import Network
        from lab.nodes import LabNode
        from lab.wire import Wire

        self._supported_lab_types = ['MERCURY', 'OSPD']
        self._unique_dict = dict()  # to make sure that all needed objects are unique
        self._nodes = list()
        self._director = None
        if config_path is None:
            return

        self._cfg = with_config.read_config_from_file(config_path=config_path)
        self._id = self._cfg['lab-id']
        self._lab_name = self._cfg['lab-name']
        self._lab_type = self._cfg['lab-type']
        if self._lab_type not in self._supported_lab_types:
            raise ValueError('"{}" is not one of supported types: {}'.format(self._lab_type, self._supported_lab_types))

        self._is_sriov = self._cfg.get('use-sr-iov', False)

        self._dns, self._ntp = self._cfg['dns'], self._cfg['ntp']
        self._neutron_username, self._neutron_password = self._cfg['special-creds']['neutron_username'], self._cfg['special-creds']['neutron_password']

        self._nets = {net_id: Network.add_network(lab=self, net_id=net_id, net_desc=net_desc) for net_id, net_desc in self._cfg['nets'].items()}

        map(lambda nd: LabNode.add_node(lab=self, node_desc=nd), self._cfg['nodes'])  # first pass - just create nodes
        map(lambda n: n.connect_node(), self._nodes)  # second pass - process wires and nics section to connect node to peers

        for peer_link in self._cfg['peer-links']:  # list of {'own-id': 'n97', 'own-port': '1/46', 'port-channel': 'pc100', 'peer-id': 'n98', 'peer-port': '1/46'}
            from_node = self.get_node_by_id(peer_link['own-id'])
            Wire.add_wire(local_node=from_node, local_port_id=peer_link['own-port'], peer_desc={'peer-id': peer_link['peer-id'], 'peer-port': peer_link['peer-port'], 'port-channel': peer_link['port-channel']})
        self.check_uniqueness()

    def check_uniqueness(self):
        from lab.nodes.lab_server import LabServer
        from lab.nodes.virtual_server import VirtualServer

        for net in self.get_all_nets().values():
            self.make_sure_that_object_is_unique(obj=net.get_vlan_id(), node_id=net)
            self.make_sure_that_object_is_unique(obj=net.get_cidr(), node_id=net)
            self.make_sure_that_object_is_unique(obj=net.get_mac_pattern(), node_id=net)

        for node in self._nodes:
            if isinstance(node, LabServer) and not isinstance(node, VirtualServer):
                for nic in node.get_nics().values():
                    self.make_sure_that_object_is_unique(obj=nic.get_ip_with_prefix(), node_id=node.get_node_id())
                    for mac in nic.get_macs():
                        self.make_sure_that_object_is_unique(obj=mac.lower(), node_id=node.get_node_id())  # check that all MAC are unique
            for wire in node.get_all_wires():
                peer_node = wire.get_peer_node(node)
                peer_port_id = wire.get_peer_port(node)
                self.make_sure_that_object_is_unique(obj='{}-{}'.format(peer_node.get_node_id(), peer_port_id), node_id=node.get_node_id())  # check that this peer_node-peer_port is unique

    def is_sriov(self):
        return self._is_sriov

    @staticmethod
    def get_role_class(role):
        from lab.nodes.fi import FI, FiDirector, FiController, FiCompute, FiCeph
        from lab.nodes.n9k import Nexus
        from lab.nodes.asr import Asr
        from lab.nodes.tor import Tor, Oob, Pxe, Terminal
        from lab.nodes.cobbler import CobblerServer
        from lab.nodes.cimc_server import CimcDirector, CimcController, CimcCompute, CimcCeph
        from lab.nodes.xrvr import Xrvr
        from lab.nodes.vtf import Vtf
        from lab.nodes.vtc import VtsHost
        from lab.nodes.vtc import Vtc

        role = role.lower()
        roles = {Oob.ROLE: Oob, Pxe.ROLE: Pxe, Tor.ROLE: Tor, Terminal.ROLE: Terminal, CobblerServer.ROLE: CobblerServer,
                 Asr.ROLE: Asr, Nexus.ROLE: Nexus, FI.ROLE: FI,
                 FiDirector.ROLE: FiDirector, FiController.ROLE: FiController, FiCompute.ROLE: FiCompute, FiCeph.ROLE: FiCeph,
                 CimcDirector.ROLE: CimcDirector, CimcController.ROLE: CimcController, CimcCompute.ROLE: CimcCompute, CimcCeph.ROLE: CimcCeph,
                 VtsHost.ROLE: VtsHost, Vtc.ROLE: Vtc, Xrvr.ROLE: Xrvr, Vtf.ROLE: Vtf}

        try:
            return roles[role]
        except KeyError:
            raise ValueError('role "{0}" is not known,  should be one of: {1}'.format(role, roles.keys()))

    def get_id(self):
        return self._id

    def get_all_nets(self):
        return self._nets

    def get_net(self, net_id):
        return self._nets[net_id]

    def get_nodes_by_class(self, klass=None):
        if klass:
            classes = klass if type(klass) is list else [klass]
            nodes = []
            for klass in classes:
                nodes += filter(lambda x: isinstance(x, klass), self._nodes)
            return nodes
        else:
            return self._nodes

    def get_node_by_id(self, node_id):
        nodes = list(filter(lambda x: x.get_node_id() == node_id, self._nodes))
        if len(nodes) == 1:
            return nodes[0]
        else:
            raise ValueError('Something strange with node_id={0}, list of nodes with this id: {1}'.format(node_id, nodes))

    def get_director(self):
        from lab.nodes.cimc_server import CimcDirector
        from lab.nodes.fi import FiDirector

        return filter(lambda x: type(x) in [CimcDirector, FiDirector], self._nodes)[0] or self.get_controllers()[0]

    def get_cobbler(self):
        from lab.nodes.cobbler import CobblerServer

        return filter(lambda x: type(x) in [CobblerServer], self._nodes)[0]

    def get_vts_hosts(self):
        from lab.nodes.vtc import VtsHost

        return filter(lambda x: type(x) is VtsHost, self._nodes)

    def get_vtc(self):
        from lab.nodes.vtc import Vtc

        return filter(lambda x: type(x) is Vtc, self._nodes)

    def get_xrvr(self):
        from lab.nodes.xrvr import Xrvr

        return filter(lambda x: type(x) is Xrvr, self._nodes)

    def get_vft(self):
        from lab.nodes.vtf import Vtf

        return filter(lambda x: type(x) is Vtf, self._nodes)

    def get_n9k(self):
        from lab.nodes.n9k import Nexus

        return filter(lambda x: type(x) is Nexus, self._nodes)

    def get_controllers(self):
        from lab.nodes.cimc_server import CimcController
        from lab.nodes.fi import FiController

        return filter(lambda x: type(x) in [CimcController, FiController], self._nodes)

    def get_computes(self):
        from lab.nodes.cimc_server import CimcCompute
        from lab.nodes.fi import FiCompute

        return filter(lambda x: type(x) in [CimcCompute, FiCompute], self._nodes)

    def get_cimc_servers(self):
        from lab.nodes.cimc_server import CimcServer

        return self.get_nodes_by_class(klass=CimcServer)

    def get_neutron_creds(self):
        return self._neutron_username, self._neutron_password

    def get_ucsm_nets_with_pxe(self):
        return [x for x in self._cfg['nets'].keys() if 'pxe' in x]

    def get_vlan_range(self):
        return self._cfg['vlan_range']

    def count_role(self, role_name):
        return len([x for x in self._nodes if role_name in x.role()])

    def logstash_creds(self):
        return self._cfg['logstash']

    def make_sure_that_object_is_unique(self, obj, node_id):
        """check that given object is unique
        :param obj: object
        :param node_id: node which tries to register the object
        """

        key = str(obj)
        if key in self._unique_dict.keys():
            raise ValueError('{} node tries to own {} which is already in use by {}'.format(node_id, key, self._unique_dict[key]))
        else:
            self._unique_dict[key] = node_id

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
        for node in self.get_xrvr():
            ip, xrvr_username, xrvr_password = node.get_xrvr_ip_user_pass()
            xrvr_ips.append(ip)

        for node in [self.get_director()] + self.get_vts_hosts():
            ip, username, _ = node.get_ssh()
            inventory[node.get_id()] = {'hosts': [ip], 'vars': {'ansible_ssh_user': username, 'ansible_ssh_private_key_file': KEY_PRIVATE_PATH,
                                                                'xrvr_ip_mx': xrvr_ips, 'xrvr_username': xrvr_username, 'xrvr_password': xrvr_password}}

        for node in self.get_n9k():
            ip, username, password = node.get_oob()
            inventory[node.get_id()] = {'hosts': [ip], 'vars': {'ansible_ssh_user': username, 'ansible_ssh_pass': password}}

        return inventory

    def lab_validate(self):
        map(lambda x: x.r_verify_oob(), self.get_nodes_by_class())
        map(lambda x: x.n9_validate(), self.get_n9k())

    def r_deploy_ssh_public(self):
        for node in self.get_director() + self.get_vts_hosts():
            node.r_deploy_ssh_key()

    def r_border_leaf(self):
        for node in self.get_n9k() + self.get_xrvr():
            node.r_border_leaf()

    def r_collect_information(self, regex, comment):
        logs = 'LOGS:\n'
        configs = '\n\nCONFIGS:\n'
        cloud_version, vts_version = self.r_get_version()
        self.log_to_artifact(name='{}-version.txt'.format(self), body='Version={}\n{}'.format(cloud_version, vts_version))
        for node in self.get_nodes_by_class():
            if hasattr(node, 'r_collect_logs'):
                logs += node.r_collect_logs(regex=regex)
            if hasattr(node, 'r_collect_config'):
                configs += node.r_collect_config()
        addon = '-' + '-'.join(comment.split()) if comment else ''
        self.log_to_artifact(name='lab-{}{}.txt'.format(self, addon), body=logs + configs)
        self.log_to_artifact(name='configs-{}{}.txt'.format(self, addon), body=configs)

    def r_get_version(self):
        cloud_version = self.get_director().r_get_version()
        vts_version = self.get_vtc()[0].r_vtc_get_version()
        return cloud_version, vts_version

    def save_lab_config(self):
        import functools

        with self.open_artifact(name='saved_{}.yaml'.format(self._lab_name), mode='w') as f:
            f.write('lab-id: {} # integer in ranage (0,99). supposed to be unique in current L2 domain since used in MAC pools\n'.format(self.get_id()))
            f.write('lab-name: {} # any string to be used on logging\n'.format(self._lab_name))
            f.write('lab-type: {} # supported types: MERCURY, OSPD\n'.format(self._lab_type))
            f.write('description-url: "{}"\n'.format(self._lab_name))
            f.write('\n')
            f.write('dns: [171.70.168.183]\n')
            f.write('ntp: [171.68.38.66]\n')
            f.write('\n')

            f.write('networks: [\n')
            f.write('\n]\n\n')

            f.write('nodes: [\n')
            node_bodies = [node.get_yaml_body() for node in self.get_nodes_by_class()]
            f.write(',\n\n'.join(node_bodies))
            f.write('\n]\n\n')

            f.write('peer-links: [ # Section which describes peer-links in the form {own-id: n92, own-port:  1/46, peer-id: n91, peer-port: 1/46, port-channel: pc100}\n   ')

            peer_links = []

            for wire in set(functools.reduce(lambda lst, x: lst + x.get_peer_link_wires(), self.get_n9k(), [])):
                peer_links.append(wire.get_peer_link_yaml_body())
            f.write(',\n   '.join(peer_links))
            f.write('\n]\n')

    def exe(self, cmd):
        from lab.nodes.lab_server import LabServer

        return {node.get_id(): node.exe(cmd) for node in self.get_nodes_by_class(LabServer)}
