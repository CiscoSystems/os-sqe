from lab.with_config import WithConfig
from lab.with_log import WithLogMixIn


class LabConfigurator(WithConfig, WithLogMixIn):
    def sample_config(self):
        pass

    def __init__(self):
        from lab.network import Network
        super(LabConfigurator, self).__init__()

        self._nets = {'api':        Network(net_id='a', cidr='10.10.10.0/32', vlan=9999, is_via_tor=True,  lab='', roles_must_present=['CimcDirector', 'CimcController', 'Vtc']),
                      'management': Network(net_id='m', cidr='11.11.11.0/24', vlan=2011, is_via_tor=False, lab='', roles_must_present=['CimcDirector', 'CimcController', 'CimcCompute', 'CimcCeph', 'CimcCompute',
                                                                                                                                       'Vtc', 'Xrvr', 'VtsHost']),
                      'tenant':     Network(net_id='t', cidr='22.22.22.0/24', vlan=2022, is_via_tor=False, lab='', roles_must_present=['CimcCompute', 'Xrvr', 'VtsHost']),
                      'storage':    Network(net_id='s', cidr='33.33.33.0/24', vlan=2033, is_via_tor=False, lab='', roles_must_present=['CimcController', 'CimcCompute', 'CimcCeph']),
                      'external':   Network(net_id='e', cidr='44.44.44.0/24', vlan=2044, is_via_tor=False, lab='', roles_must_present=['CimcController']),
                      'provider':   Network(net_id='p', cidr='55.55.55.0/24', vlan=2055, is_via_tor=False, lab='', roles_must_present=['CimcCompute'])}
        self.execute_mercury()

    def execute_mercury(self):
        from lab.laboratory import Laboratory

        mercury_cfg = self.ask_mercury_setup_data()
        nets_cfg = self.process_mercury_nets(mercury_cfg=mercury_cfg)
        switches_cfg = self.process_mercury_switches(mercury_cfg=mercury_cfg)
        nodes_cfg, virtuals_cfg = self.process_mercury_nodes(mercury_cfg=mercury_cfg)
        sqe_cfg = {'lab-name': mercury_cfg['TESTING_TESTBED_NAME'] + '-' + mercury_cfg['MECHANISM_DRIVERS'].lower(), 'lab-id': 99, 'lab-type': 'MERCURY-' + mercury_cfg['MECHANISM_DRIVERS'].upper(),
                   'dns': ['171.70.168.183'], 'ntp': ['171.68.38.66'],
                   'special-creds': {'neutron_username': 'admin', 'neutron_password': 'new123'},
                   'networks': nets_cfg, 'switches': switches_cfg, 'nodes': nodes_cfg, 'virtuals': virtuals_cfg, 'wires': []}
        lab = Laboratory(sqe_cfg)

        sqe_cfg['wires'] = self.process_connections(lab=lab)
        sqe_cfg['switches'][0]['oob-ip'] = lab.get_oob().get_oob()[0]
        sqe_cfg['switches'][1]['oob-ip'] = lab.get_tor().get_oob()[0]

        lab = Laboratory(sqe_cfg)

        lab.save_self_config()

    @staticmethod
    def does_mercury_dir_exists(lab_name):
        import os

        mercury_testbed_dir = os.path.expanduser('~/repo/mercury/testbeds/' + lab_name + '/')
        if os.path.exists(mercury_testbed_dir):
            return mercury_testbed_dir
        else:
            raise Exception('The lab {} is not found'.format(mercury_testbed_dir))

    def ask_mercury_setup_data(self):
        import os
        from fabric.operations import prompt

        mercury_testbed_dir = prompt(text='Enter lab name:', validate=self.does_mercury_dir_exists)
        names = os.listdir(mercury_testbed_dir)
        name = prompt(text='you have {} Which yaml to use? '.format(' '.join(names)), default=names[0])

        return self.read_config_from_file(mercury_testbed_dir + name)

    @staticmethod
    def ask_ip_u_p(msg):
        from fabric.operations import prompt
        import validators

        while True:
            ip4 = prompt(text=msg + ' enter IP or none > ')
            if ip4 == 'none':
                return None, None, None
            if validators.ipv4(ip4):
                break
        username = prompt(text=msg + ' enter username > ', default='admin')
        password = prompt(text=msg + ' enter password > ')
        return ip4, username, password

    def process_connections(self, lab):
        n9_statuses = [n9.n9_show_all() for n9 in lab.get_n9k()]

        cimc_port_id_mac_lst = []
        for cimc in lab.get_cimc_servers():
            r = cimc.cimc_list_all_nics()
            for port_id, mac in r.items():
                cimc_port_id_mac_lst.append({'cimc-node': cimc, 'cimc-port-id': port_id, 'cimc-mac': mac})

        wires_cfg = []
        for cimc_port_id_mac in cimc_port_id_mac_lst:
            cimc_node = cimc_port_id_mac['cimc-node']
            cimc_port_id = cimc_port_id_mac['cimc-port-id']
            cimc_mac = cimc_port_id_mac['cimc-mac']

            for n9st in n9_statuses:
                nei = n9st.find_mac(mac=cimc_mac)
                n9_node_id = n9st.get_n9_node_id() if nei else 'not_connected'
                n9_port_id = nei.get_n9_port_id() if nei else 'not_connected'
                n9_pc_id = n9st.get_n9_pc_id(n9_port_id) if nei else 'not_connected'
                wires_cfg.append({'from-node-id': cimc_node.get_node_id(), 'from-port-id': cimc_port_id, 'from-mac': cimc_mac, 'to-node-id': n9_node_id, 'to-port-id': n9_port_id, 'to-mac': 'unknown', 'pc-id': n9_pc_id})

                # global_vlans = filter(lambda net: net.is_via_tor(), lab.get_all_nets().values())
                # a = n9.n9_cmd('sh spanning-tree vlan {}'.format(global_vlans[0].get_vlan_id()))
            # uplink_candidate_pc_id = [x['if_index'] for x in a.values()[0][u'TABLE_port'][u'ROW_port'] if x['role'] == 'root'][0]
            # uplink_candidate_port_ids = [x['port'] for x in r['ports'][uplink_candidate_pc_id]['ports']]
            # for cdp in r['cdp']:
            #     n9_port_id = cdp.get('intf_id')
            #     n9_mac = 'unknown'
            #     peer_port_id = cdp.get('port_id')
            #     peer_ip = cdp.get('v4mgmtaddr')
            #     peer_mac = 'unknown'
            #     n9_pc_id = 'unknown'
            #
            #     if n9_port_id == 'mgmt0':
            #         peer = lab.get_oob()
            #         peer.set_oob_creds(ip=peer_ip, username='openstack-read', password='CTO1234!')
            #     elif n9_port_id in uplink_candidate_port_ids:
            #         peer = lab.get_tor()
            #         peer.set_oob_creds(ip=peer_ip, username='openstack-read', password='CTO1234!')
            #     else:  # assuming here that all others are peer link
            #         peer = [x for x in lab.get_n9k() if x.get_oob()[0] == peer_ip]
            #         if len(peer) != 1:
            #             continue  # assume that this device is not a part of the lab
            #         peer = peer[0]
            #     wires_cfg.append({'from-node-id': n9.get_node_id(), 'from-port-id': n9_port_id, 'from-mac': n9_mac, 'to-node-id': peer.get_node_id(), 'to-port-id': peer_port_id, 'to-mac': peer_mac, 'pc-id': n9_pc_id})

        return sorted(wires_cfg, key=lambda e: e['from-node-id'])

    def process_mercury_nets(self, mercury_cfg):

        for mercury_net_id, net in self._nets.items():
            net_mercury_cfg = filter(lambda k: k['segments'][0] == mercury_net_id, mercury_cfg['NETWORKING']['networks'])
            if net_mercury_cfg:
                cidr = net_mercury_cfg[0].get('subnet')
                vlan_id = net_mercury_cfg[0]['vlan_id']
                net.set_vlan(vlan_id)
                if cidr:
                    net.set_cidr(cidr)
                    net.set_via_tor(cidr[:2] not in ['11', '22', '33', '44', '55'])

        return [{'net-id': x.get_net_id(), 'vlan': x.get_vlan_id(), 'cidr': x.get_cidr(), 'should-be': x.get_roles(), 'is-via-tor': x.is_via_tor()} for x in self._nets.values()]

    @staticmethod
    def process_mercury_switches(mercury_cfg):

        switches = [{'node-id': 'oob', 'role': 'oob', 'oob-ip': '1.1.1.1', 'oob-username': 'openstack-read', 'oob-password': 'CTO1234!', 'ssh-username': None, 'ssh-password': None, 'proxy-id': None},
                    {'node-id': 'tor', 'role': 'tor', 'oob-ip': '1.1.1.2', 'oob-username': 'openstack-read', 'oob-password': 'CTO1234!', 'ssh-username': None, 'ssh-password': None, 'proxy-id': None}]

        for i, sw in enumerate(mercury_cfg['TORSWITCHINFO']['SWITCHDETAILS'], start=97):
            switches.append({'node-id': 'n' + chr(i), 'role': 'VimTor', 'oob-ip': sw['ssh_ip'], 'oob-username': sw['username'], 'oob-password': sw['password'], 'ssh-username': 'None', 'ssh-password': 'None', 'proxy-id': None})

        ip, username, password = LabConfigurator.ask_ip_u_p(msg='Mercury usually has the third switch used to connect MGM node to outer world')

        if ip:
            switches.append({'node-id': 'nc', 'role': 'VimCatalist', 'oob-ip': ip, 'oob-username': username, 'oob-password': password, 'ssh-username': 'None', 'ssh-password': 'None', 'proxy-id': None})

        return switches

    def process_mercury_nodes(self, mercury_cfg):
        cimc_username = mercury_cfg['CIMC-COMMON']['cimc_username']
        cimc_password = mercury_cfg['CIMC-COMMON']['cimc_password']
        ssh_username = mercury_cfg['COBBLER']['admin_username']
        ssh_password = 'cisco123'

        nodes = [{'node-id': 'mgm', 'role': 'CimcDirector', 'oob-ip': mercury_cfg['TESTING_MGMT_NODE_CIMC_IP'], 'oob-username': mercury_cfg['TESTING_MGMT_CIMC_USERNAME'], 'oob-password': mercury_cfg['TESTING_MGMT_CIMC_PASSWORD'],
                  'ssh-username': ssh_username, 'ssh-password': ssh_password, 'proxy-id': None,
                  'nics': [{'nic-id': 'a', 'ip': mercury_cfg['TESTING_MGMT_NODE_API_IP'].split('/')[0], 'is-ssh': True},
                           {'nic-id': 'm', 'ip': mercury_cfg['TESTING_MGMT_NODE_MGMT_IP'].split('/')[0], 'is-ssh': False}]}]

        virtuals = []

        for mercury_role_id, mercury_node_ids in mercury_cfg['ROLES'].items():
            sqe_role_id = {'control': 'CimcController', 'compute': 'CimcCompute', 'block_storage': 'CimcCeph', 'vts': 'VtsHost'}[mercury_role_id]

            nets_for_this_role = {mercury_net_id: net for mercury_net_id, net in self._nets.items() if sqe_role_id in net.get_roles()}

            for i, node_id in enumerate(mercury_node_ids, start=1):
                try:
                    mercury_srv_cfg = mercury_cfg['SERVERS'][node_id]
                    oob_ip = mercury_srv_cfg['cimc_info']['cimc_ip']
                    oob_username = mercury_srv_cfg['cimc_info'].get('cimc_username', cimc_username)
                    oob_password = mercury_srv_cfg['cimc_info'].get('cimc_password', cimc_password)

                    nics = []
                    for mercury_net_id, net in nets_for_this_role.items():
                        ip_base = {'control': 10, 'compute': 20, 'ceph': 30, 'vts': 40}[mercury_role_id] if net.is_via_tor() else 4
                        ip = mercury_srv_cfg.get(mercury_net_id + '_ip', str(net.get_ip_for_index(ip_base + i)))
                        nics.append({'nic-id': mercury_net_id[0], 'ip': ip, 'is-ssh': mercury_net_id == 'management'})

                    nodes.append({'node-id': node_id, 'role': sqe_role_id, 'oob-ip': oob_ip, 'oob-username': oob_username, 'oob-password': oob_password, 'ssh-username': ssh_username, 'ssh-password': ssh_password,
                                  'proxy-id': 'mgm', 'nics': nics})

                    if mercury_role_id == 'vts':
                        vtc_nics = [{'nic-id': 'a', 'ip': mercury_cfg['VTS_PARAMETERS']['VTS_VTC_API_IPS'][i-1], 'is-ssh': True},
                                    {'nic-id': 'm', 'ip': mercury_cfg['VTS_PARAMETERS']['VTS_VTC_MGMT_IPS'][i-1], 'is-ssh': False}]
                        xrvr_nics = [{'nic-id': 'm', 'ip': mercury_cfg['VTS_PARAMETERS']['VTS_XRNC_MGMT_IPS'][i-1], 'is-ssh': True},
                                     {'nic-id': 't', 'ip': mercury_cfg['VTS_PARAMETERS']['VTS_XRNC_TENANT_IPS'][i-1], 'is-ssh': False}]

                        virtuals.append({'node-id': 'vtc' + str(i), 'role': 'vtc', 'oob-ip': None, 'oob-username': oob_username, 'oob-password': mercury_cfg['VTS_PARAMETERS']['VTS_PASSWORD'],
                                         'ssh-username': 'admin', 'ssh-password': ssh_password,
                                         'virtual-on': node_id, 'vip_a': mercury_cfg['VTS_PARAMETERS']['VTS_VTC_API_VIP'], 'vip_m': mercury_cfg['VTS_PARAMETERS']['VTS_NCS_IP'], 'proxy-id': None, 'nics': vtc_nics})
                        virtuals.append({'node-id': 'xrvr' + str(i), 'role': 'xrvr', 'oob-ip': None, 'oob-username': oob_username, 'oob-password': oob_password, 'ssh-username': ssh_username, 'ssh-password': ssh_password,
                                         'virtual-on': node_id, 'proxy-id': 'mgm', 'nics': xrvr_nics})
                except KeyError as ex:
                    raise KeyError('{}: no {}'.format(node_id, ex))
        return nodes, virtuals

