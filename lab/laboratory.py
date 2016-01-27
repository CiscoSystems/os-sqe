import tempfile
from lab import with_config


class Laboratory(with_config.WithConfig):

    temp_dir = tempfile.mkdtemp(prefix='runner-ha-')

    def sample_config(self):
        pass

    def __init__(self, config_path):
        from netaddr import IPNetwork
        from lab.server import Server
        from lab.providers.n9k import Nexus

        import validators

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
        shift_user = 4  # need to start from -2 due to IPNetwork[-1] is broadcast address
        shift_ipmi = 4  # need to start from 4 due to IPNetwork[0-1-2-3] are network and gw addresses
        for x in self.cfg['nodes']:
            for role, val in x.iteritems():
                for role_counter, server_id in enumerate(val['server-id']):
                    server = Server(ip=user_net[-2] if 'director' in role else user_net[shift_user],
                                    hostname='g{0}-director.ctocllab.cisco.com'.format(self.cfg['lab-id']),
                                    username=self.cfg['username'],
                                    net=user_net,
                                    role=role,
                                    n_in_role=role_counter)
                    if validators.ipv4(server_id):
                        server._tmp_dir_exists = True
                        server_id_short = server_id.split('.')[-1]
                        b_c_id = 'A0:{0}'.format(int(server_id_short))
                        server.set_ipmi(ip=server_id, username=self.cfg['cimc'][server_id]['username'],
                                        password=self.cfg['cimc'][server_id]['password'])
                        server.set_cimc(self.cfg['cimc'][server_id]['n9k'],
                                        self.cfg['cimc'][server_id]['n9k_port'],
                                        self.cfg['cimc'][server_id]['pci_slot'],
                                        self.cfg['cimc'][server_id]['uplink_port'])
                        self.servers_controlled_by_cimc.append(server)
                    else:
                        if '/' in server_id:
                            b_c_id = 'B{0}:{1:02}'.format(int(server_id.split('/')[0]), int(server_id.split('/')[1]))
                        else:
                            b_c_id = 'C0:{0:02}'.format(int(server_id))
                        profile = 'G{0}-{1}-{2}'.format(self.cfg['lab-id'], b_c_id.replace(':', '-'), role)
                        server.set_ucsm(ip=self.cfg['ucsm']['host'], username=self.cfg['ucsm']['username'], password=self.cfg['ucsm']['password'],
                                        service_profile=profile, server_id=server_id, is_sriov=val.get('is-sriov', False))
                        server.set_ipmi(ip=ipmi_net[shift_ipmi], username=self.cfg['cobbler']['username'], password=self.cfg['cobbler']['password'])
                        self.servers_controlled_by_ucsm.append(server)
                    for order, nic_name in enumerate(val['nets'], start=1):
                        mac = self.cfg['nets'][nic_name]['mac-tmpl'].format(lab_id=self.cfg['lab-id'], b_c_id=b_c_id)
                        server.add_if(nic_name=nic_name, nic_mac=mac, nic_order=order, nic_vlans=self.cfg['nets'][nic_name]['vlan'])
                    shift_user += 1
                    shift_ipmi += 1
        self.net_nodes = [Server(ip=self.cfg['ucsm']['host'], username=self.cfg['ucsm']['username'], password=self.cfg['ucsm']['password'], role='ucsm', n_in_role=0),
                          Server(ip=self.cfg['n9k']['host1'], username=self.cfg['n9k']['username'], password=self.cfg['n9k']['password'], role='n9k', n_in_role=1),
                          Server(ip=self.cfg['n9k']['host2'], username=self.cfg['n9k']['username'], password=self.cfg['n9k']['password'], role='n9k', n_in_role=2)
                          ]
        self.n9ks = {self.cfg['n9k']['host1']: Nexus(self.cfg['n9k']['host1'], self.cfg['n9k']['username'], self.cfg['n9k']['password'],
                                                     [self.cfg['n9k_fi']['n9k1_ucsm1'][0], self.cfg['n9k_fi']['n9k1_ucsm2'][0]], self.cfg['n9k']['peer_int']),
                     self.cfg['n9k']['host2']: Nexus(self.cfg['n9k']['host2'], self.cfg['n9k']['username'], self.cfg['n9k']['password'],
                                                     [self.cfg['n9k_fi']['n9k1_ucsm1'][0], self.cfg['n9k_fi']['n9k2_ucsm2'][0]], self.cfg['n9k']['peer_int'])}

        self._user_net_range = user_net[4], user_net[-3]  # will be provided to OSP7 deployer as a range for vip and controllers -2 is director

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

    def ucsm_creds(self):
        return self.cfg['ucsm']['host'], self.cfg['ucsm']['username'], self.cfg['ucsm']['password']

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
        return self.cfg['nets']['eth1']['vlan'][1]

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
