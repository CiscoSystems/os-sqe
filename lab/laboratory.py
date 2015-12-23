from lab import WithConfig


class Laboratory(WithConfig.WithConfig):
    def sample_config(self):
        pass

    def __init__(self, config_path):
        from netaddr import IPNetwork
        from lab.Server import Server

        super(Laboratory, self).__init__(config=None)

        self.cfg = self.read_config_from_file(config_path=config_path)
        self.id = self.cfg['lab-id']
        with open(WithConfig.KEY_PUBLIC_PATH) as f:
            self.public_key = f.read()

        user_net = IPNetwork(self.cfg['nets']['user']['cidr'])
        self.user_gw = user_net[1]

        ipmi_net = IPNetwork(self.cfg['nets']['ipmi']['cidr'])
        self.ipmi_gw = ipmi_net[1]
        self.ipmi_netmask = ipmi_net.netmask

        self.servers = []
        shift_user = -2  # need to start from -2 due to IPNetwork[-1] is broadcast address
        shift_ipmi = 4  # need to start from 4 due to IPNetwork[0-1-2-3] are network and gw addresses
        for x in self.cfg['nodes']:
            for role, val in x.iteritems():
                for role_counter, server_id in enumerate(val['server-id']):
                    server = Server(ip=user_net[shift_user],
                                    hostname='g{0}-director.ctocllab.cisco.com'.format(self.cfg['lab-id']),
                                    net=user_net,
                                    role=role,
                                    n_in_role=role_counter)

                    if '/' in server_id:
                        b_c_id = 'B{0}:{1:02}'.format(int(server_id.split('/')[0]), int(server_id.split('/')[1]))
                    else:
                        b_c_id = 'C0:{0:02}'.format(int(server_id))

                    profile = 'G{0}-{1}-{2}'.format(self.cfg['lab-id'], b_c_id.replace(':', '-'), role)

                    server.set_ucsm(ip=self.cfg['ucsm']['host'], username=self.cfg['ucsm']['username'], password=self.cfg['ucsm']['password'],
                                    service_profile=profile, server_id=server_id, is_sriov=val.get('is-sriov', False))
                    server.set_ipmi(ip=ipmi_net[shift_ipmi], username=self.cfg['cobbler']['username'], password=self.cfg['cobbler']['password'])
                    for order, nic_name in enumerate(val['nets'], start=1):
                        mac = self.cfg['nets'][nic_name]['mac-tmpl'].format(lab_id=self.cfg['lab-id'], b_c_id=b_c_id)
                        server.add_if(nic_name=nic_name, nic_mac=mac, nic_order=order, nic_vlans=self.cfg['nets'][nic_name]['vlan'])
                    self.servers.append(server)
                    shift_user -= 1
                    shift_ipmi += 1
        self._user_net_free_range = user_net[4], user_net[shift_user]

    def director(self):
        return self.servers[0]

    def all_but_director(self):
        return self.servers[1:]

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
        return self.cfg['nets']['user']['vlan'][0]

    def n9k_creds(self):
        return self.cfg['n9k']['host1'], self.cfg['n9k']['host2'], self.cfg['n9k']['username'], self.cfg['n9k']['password']

    def user_net_cidr(self):
        return self.cfg['nets']['user']['cidr']

    def user_net_free_range(self):
        return self._user_net_free_range

    def count_role(self, role_name):
        return len([x for x in self.servers if role_name in x.role])
