import tempfile

from netaddr import IPNetwork

from lab import with_config
from lab.cimc import Cimc
from lab.fi import FI
from lab.port import Port
from lab.providers.n9k import Nexus
from lab.server import Server


class Laboratory(with_config.WithConfig):

    temp_dir = tempfile.mkdtemp(prefix='runner-ha-')

    def sample_config(self):
        pass

    def __init__(self, config_path):


        super(Laboratory, self).__init__(config=None)

        self.cfg = self.read_config_from_file(config_path=config_path)
        self.id = self.cfg['lab-id']
        with open(with_config.KEY_PUBLIC_PATH) as f:
            self.public_key = f.read()

        user_net = IPNetwork(self.cfg['nets']['user']['cidr'])
        self.user_gw = user_net[1]

        ipmi_net = IPNetwork(self.cfg['nets']['ipmi']['cidr'])
        self.ipmi_gw = ipmi_net[1]
        self.ipmi_netmask = ipmi_net.netmask
        self.servers_controlled_by_ucsm = []
        self.servers_controlled_by_cimc = []
        self.all_nodes = dict()
        shift_user = 4  # need to start from -2 due to IPNetwork[-1] is broadcast address
        shift_ipmi = 4  # need to start from 4 due to IPNetwork[0-1-2-3] are network and gw addresses
        for name, value in self.cfg['nodes'].iteritems():
            role_counter = name.split('-')[1]
            role_name = name.split('-')[0]

            if role_name in ['control', 'compute', 'director', 'ceph']:
                server = Server(name, ip=user_net[-2] if 'director' in role_name else user_net[shift_user],
                                    lab=self,
                                    hostname='g{0}-director.ctocllab.cisco.com'.format(self.cfg['lab-id']),
                                    username=self.cfg['username'],
                                    net=user_net,
                                    role=role_name,
                                    n_in_role=role_counter)
                self.all_nodes[name] = server
                if value.get('cimc-ip', False):
                    server_control = Cimc(name, value['cimc-ip'], value['username'], value['password'], self)
                    self.all_nodes[value['cimc-ip']] = server_control
                    server.set_cimc_or_ucsm(server_control)
                    self.servers_controlled_by_cimc.append(server)
                else:
                    self.servers_controlled_by_ucsm.append(server)
                shift_user += 1
                shift_ipmi += 1
            elif role_name == 'Nexus':
                self.all_nodes[value['ip']] = Nexus(name, value['ip'], value['username'], value['password'], self)
            elif role_name == 'FI':
                self.all_nodes[value['ip']] = FI(name, value['ip'], value['username'], value['password'], self, value['vip'])

        for node_name, node_entry in self.cfg['nodes'].iteritems():
            if node_entry.get('ports', False):
                node = self.all_nodes[node_entry['ip']]
                for port_no, other_port in node_entry['ports'].iteritems():
                    port = Port(node, port_no)
                    another_node_name = self.cfg['nodes'][other_port['node']].get('ip', False) or other_port['node']
                    another_node = self.all_nodes[another_node_name]
                    port.connect_port(Port(another_node, other_port['port']))
                    # Add node UCSM to control
                    if isinstance(node, FI):
                        [server.set_cimc_or_ucsm(node) for server in self.servers_controlled_by_ucsm]
                        self.ucsm = node

    def get_ucsm(self):
        for node in self.all_nodes.itervalues():
            if isinstance(node, FI):
                return node

    def director(self):
        return self.servers()[0]

    def all_but_director(self):
        return self.servers()[1:]

    def return_all_vlans(self):
        vlan_set = set()
        vlan_set.update([interface['vlan'] for interface in self.cfg['nets'].itervalues()])
        return vlan_set

    def return_vlans_by_server(self, server):
        vlan_set = set()
        [vlan_set.update(y) for y in [self.cfg['nets'][x['nic_name']]['vlan'] for x in server.get_nics()]]
        return vlan_set

    def _servers_for_role(self, role):
        return [x for x in self.servers()[1:] if x.role == role]

    def particular_node(self, name):
        for server in self.servers() + self.net_nodes:
            if name in server.name():
                return server
        raise RuntimeError('No server {0}'.format(name))

    def controllers(self):
        return self._servers_for_role(role='control')

    def computes(self):
        return self._servers_for_role(role='compute')

    def nodes_controlled_by_ucsm(self):
        return self.servers_controlled_by_ucsm

    def nodes_controlled_by_cimc(self):
        return self.servers_controlled_by_cimc

    def servers(self):
        return self.servers_controlled_by_ucsm + self.servers_controlled_by_cimc

    def ucsm_uplink_ports(self):
        return self.cfg['ucsm']['uplink-ports']

    def ucsm_uplink_vpc_id(self):
        return self.cfg['ucsm']['uplink-vpc-id']

    def ucsm_creds(self, user='admin'):
        user_creads = self.cfg['ucsm']['creds'][user]
        return self.cfg['ucsm']['host'], user_creads['username'], user_creads['password']

    def ucsm_vlans(self):
        vlans = []
        map(lambda x: vlans.extend(x['vlan']), self.cfg['nets'].values())
        return set(vlans)

    def ucsm_nets_with_pxe(self):
        return [x for x in self.cfg['nets'].keys() if 'pxe' in x]

    def ucsm_is_any_sriov(self):
        return any([x.values()[0].get('is-sriov', False) for x in self.cfg['nodes']])

    def cobbler_creds(self):
        return self.cfg['cobbler']['host'], self.cfg['cobbler']['username'], self.cfg['cobbler']['password']

    def external_vlan(self):
        return self.cfg['nets']['eth1']['vlan'][1]

    def testbed_vlan(self):
        return self.cfg['nets']['pxe-int']['vlan'][1]

    def storage_vlan(self):
        return self.cfg['nets']['pxe-int']['vlan'][2]

    def storage_mgmt_vlan(self):
        return self.cfg['nets']['pxe-int']['vlan'][3]

    def tenant_network_vlan(self):
        return self.cfg['nets']['pxe-int']['vlan'][4]

    def overcloud_floating_vlan(self):
        return self.cfg['nets']['eth1']['vlan'][0]

    def vlan_range(self):
        return self.cfg['vlan_range']

    def n9k_creds(self):
        return self.cfg['n9k']['host1'], self.cfg['n9k']['host2'], self.cfg['n9k']['username'], self.cfg['n9k']['password']

    def user_net_cidr(self):
        return self.cfg['nets']['user']['cidr']

    def user_net_free_range(self):
        return self._user_net_range

    def count_role(self, role_name):
        return len([x for x in self.servers() if role_name in x.role])

    def logstash_creds(self):
        return self.cfg['logstash']
