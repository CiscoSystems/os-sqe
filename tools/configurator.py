from lab.with_config import WithConfig
from lab.with_log import WithLogMixIn


class Configurator(WithConfig, WithLogMixIn):
    KNOWN_EXT_VLANS = {
        6:    '172.31.230.0/24',     # ipmi cobbler
        112:  '10.30.117.0/28',      # i13 mx
        157:  '10.23.228.224/27',    # marahaika a
        319:  '10.23.221.128/26',    # g7-2 a
        690:  '172.29.68.224/28',    # g7-2 e
        860:  '172.29.86.0/26',      # i13 api
        1735: '44.44.44.0/24',       # marahaika e
        2301: '172.26.232.192/28',   # c35bot a
        2302: '172.26.232.208/28'    # c35bot e
        }

    def sample_config(self):
        pass

    def __init__(self):
        from lab.network import Network
        super(Configurator, self).__init__()

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
        switches_cfg = self.process_switches(mercury_cfg=mercury_cfg)
        nodes_cfg, virtuals_cfg = self.process_mercury_nodes(mercury_cfg=mercury_cfg)
        cfg = {'name': mercury_cfg['TESTING_TESTBED_NAME'], 'type': 'TYPE-MERCURY-' + mercury_cfg['MECHANISM_DRIVERS'].upper(),
               'special-creds': {'neutron_username': 'admin', 'neutron_password': 'new123'},
               'networks': nets_cfg, 'switches': switches_cfg, 'nodes': nodes_cfg, 'virtuals': virtuals_cfg, 'wires': [], 'setup-data': mercury_cfg}
        pod = Laboratory(cfg)

        cfg['wires'] = self.process_connections(pod=pod)

        lab = Laboratory(cfg)

        lab.save_self_config()

    def ask_mercury_setup_data(self):
        import os
        from fabric.operations import prompt

        def chunks(l, n):
            for i in range(0, len(l), n):
                yield ' * '.join(l[i:i + n])

        repo_dir = os.path.expanduser('~/repo/mercury/testbeds')
        pods = filter(lambda x: not x.startswith('.'), os.listdir(repo_dir))

        pods_str = '\n'.join(chunks(pods, 10))

        def is_pod(n):
            if n in pods:
                return os.path.join(repo_dir, n)
            else:
                raise Exception('pod {} not found'.format(n))

        pod_dir = prompt(text='Choose one of\n' + pods_str + ' > ', validate=is_pod)
        yaml_names = os.listdir(pod_dir)
        yaml_name = prompt(text='Chosse one of\n{} >'.format(' '.join(yaml_names)), default=yaml_names[-1])
        return self.read_config_from_file(os.path.join(pod_dir, yaml_name))

    @staticmethod
    def ask_ip_u_p(msg, default):
        from fabric.operations import prompt
        import validators

        def is_ipv4(ip):
            if ip is not None and validators.ipv4(ip):
                return ip
            else:
                raise Exception('{} is not valid ipv4'.format(ip))

        ipv4 = prompt(text=msg + ' enter IP> ', default=default, validate=is_ipv4)
        if ipv4 is None:
            return None, None, None
        username = prompt(text=msg + ' enter username > ', default='admin')
        password = prompt(text=msg + ' enter password > ')
        return ipv4, username, password

    @staticmethod
    def process_connections(pod):
        import yaml

        cimc_info_yaml = Configurator.get_artifact_file_path('{}-cimc-info.yaml'.format(pod))
        try:
            cimc_info_lst = Configurator.read_config_from_file(config_path=cimc_info_yaml)
        except ValueError:
            cimc_info_lst = []
            for cimc in pod.get_cimc_servers():
                r = cimc.cimc_list_all_nics()
                for port_id, mac in r.items():
                    cimc_info_lst.append({'node-id': cimc.node_id, 'port-id': port_id, 'mac': mac})
            with Configurator.open_artifact(name=cimc_info_yaml, mode='w') as f:
                yaml.dump(cimc_info_lst, f)

        wires_cfg = []
        for cimc_info in cimc_info_lst:
            cimc_node_id = cimc_info['node-id']
            cimc_port_id = cimc_info['port-id']
            cimc_mac = cimc_info['mac']

            for n9 in pod.vim_tors:
                nei = n9.find_neighbour_with_mac(mac=cimc_mac)
                n9_node_id = n9.id if nei else 'not_connected'
                n9_port_id = nei.port.port_id if nei else 'not_connected'
                n9_pc_id = nei.port.pc_id if nei else 'not_connected'
                wires_cfg.append({'from-node-id': cimc_node_id, 'from-port-id': cimc_port_id, 'from-mac': cimc_mac, 'to-node-id': n9_node_id, 'to-port-id': n9_port_id, 'to-mac': 'unknown', 'pc-id': n9_pc_id})

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
                elif vlan_id in self.KNOWN_EXT_VLANS:
                    net.set_cidr(self.KNOWN_EXT_VLANS[vlan_id])

        return [{'net-id': x.get_net_id(), 'vlan': x.get_vlan_id(), 'cidr': x.get_cidr(), 'should-be': x.get_roles(), 'is-via-tor': x.is_via_tor()} for x in self._nets.values()]

    @staticmethod
    def process_switches(mercury_cfg):

        pod_name = mercury_cfg['TESTING_TESTBED_NAME']
        catalyst = {'g7-2': '10.23.223.176'}

        switches = []
        username, password = None, None
        for sw in mercury_cfg['TORSWITCHINFO']['SWITCHDETAILS']:
            username, password = sw['username'], sw['password']
            switches.append({'node-id': 'n' + sw['hostname'][-1].lower(), 'role': 'VimTor', 'oob-ip': sw['ssh_ip'], 'proxy-id': None,
                             'oob-username': username, 'oob-password': password,
                             'ssh-username': None, 'ssh-password': None})

        if pod_name in catalyst:
            switches.append({'node-id': 'nc', 'role': 'VimCat', 'oob-ip': catalyst[pod_name], 'oob-username': username, 'oob-password': password, 'ssh-username': 'None', 'ssh-password': 'None', 'proxy-id': None})

        switches.append({'node-id': 'oob', 'role': 'oob', 'oob-ip': '1.1.1.1', 'oob-username': 'openstack-read', 'oob-password': password, 'ssh-username': None, 'ssh-password': None, 'proxy-id': None})
        switches.append({'node-id': 'tor', 'role': 'tor', 'oob-ip': '1.1.1.2', 'oob-username': 'openstack-read', 'oob-password': password, 'ssh-username': None, 'ssh-password': None, 'proxy-id': None})

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


if __name__ == '__main__':
    c = Configurator()
