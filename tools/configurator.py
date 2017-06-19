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

    KNOWN_SPECIALS = {
        'g7-2': [{'node': 'term', 'role': 'terminal', 'oob-ip': '172.31.229.55', 'oob-username': 'openstack-read'},
                 {'node': 'pxe', 'role': 'pxe', 'oob-ip': '172.31.230.170', 'oob-username': 'openstack-read'},
                 {'node': 'oob', 'role': 'oob', 'oob-ip': '172.31.230.158', 'oob-username': 'openstack-read'},
                 {'node': 'tor', 'role': 'tor', 'oob-ip': '172.31.230.235', 'oob-username': 'openstack-read'}],
        'c35bottom': [{'node': 'oob', 'role': 'oob', 'oob-ip': '172.26.232.132', 'oob-username': "admin"},
                      {'node': 'tor', 'role': 'tor', 'oob-ip': '172.26.232.132', 'oob-username': "admin"}],
        'marahaika': [{'node': 'oob', 'role': 'oob', 'oob-ip': '172.31.229.56', 'oob-username': "admin"},
                      {'node': 'tor', 'role': 'tor', 'oob-ip': '172.31.229.56', 'oob-username': "admin"}]
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
        nets = self.process_mercury_nets(mercury_cfg=mercury_cfg)
        switches, specials = self.process_switches(mercury_cfg=mercury_cfg)
        nodes, virtuals = self.process_mercury_nodes(mercury_cfg=mercury_cfg)
        pod_type = mercury_cfg['MECHANISM_DRIVERS'].lower()
        cfg = {'name': mercury_cfg['TESTING_TESTBED_NAME'] + '-' + pod_type, 'type': pod_type,
               'special-creds': {'neutron_username': 'admin', 'neutron_password': 'new123'},
               'networks': nets, 'switches': switches, 'specials': specials, 'nodes': nodes, 'virtuals': virtuals, 'wires': [], 'setup-data': mercury_cfg}
        pod = Laboratory(cfg)

        cfg['wires'] = self.process_connections(pod=pod)

        self.save_self_config(pod=Laboratory(cfg))

    @staticmethod
    def process_switches(mercury_cfg):

        pod_name = mercury_cfg['TESTING_TESTBED_NAME']
        catalyst = {'g7-2': '10.23.223.176'}

        switches = []
        username, password = None, None
        for sw in mercury_cfg['TORSWITCHINFO']['SWITCHDETAILS']:
            username, password = sw['username'], sw['password']
            switches.append({'node': 'n' + sw['hostname'][-1].lower(), 'role': 'VimTor', 'oob-ip': sw['ssh_ip'], 'oob-username': username, 'oob-password': password})

        if pod_name in catalyst:
            switches.append({'node': 'nc', 'role': 'VimCat', 'oob-ip': catalyst[pod_name], 'oob-username': username, 'oob-password': password})

        specials = []
        for x in Configurator.KNOWN_SPECIALS.get(pod_name, []):
            x['oob-password'] = password
            specials.append(x)

        return switches, specials

    def ask_mercury_setup_data(self):
        import os
        from fabric.operations import prompt

        def chunks(l, n):
            for i in range(0, len(l), n):
                yield ' * '.join(l[i:i + n])

        repo_dir = os.path.expanduser('~/repo/mercury/mercury/testbeds')
        pods = filter(lambda x: not x.startswith('.'), os.listdir(repo_dir))

        pods_str = '\n'.join(chunks(pods, 10))

        def is_pod(n):
            if n in pods:
                return os.path.join(repo_dir, n)
            else:
                raise Exception('pod {} not found'.format(n))

        pod_dir = prompt(text='Choose one of\n' + pods_str + ' > ', validate=is_pod, default='g7-2')
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
            cimc_info_dic = Configurator.read_config_from_file(config_path=cimc_info_yaml)
        except ValueError:
            cimc_info_dic = {}
            for cimc in pod.cimc_servers:
                cimc_info_dic[cimc.id] = cimc.cimc_list_all_nics()  # returns dic of {port_id: mac}
            with Configurator.open_artifact(name=cimc_info_yaml, mode='w') as f:
                yaml.dump(cimc_info_dic, f)

        wires_cfg = []
        for node1, d in cimc_info_dic.items():
            for port1, mac in d.items():
                neis = [x.find_neighbour_with_mac(mac=mac, cimc_port_id=port1) for x in pod.vim_tors + pod.vim_cat]
                neis = filter(lambda n: n is not None, neis)
                if neis:
                    assert len(neis) == 1, 'More then 1 switch is found connected to the {} {}'.format(node1, port1)
                    nei = neis[0]
                    wires_cfg.append({'node1': node1, 'port1': port1, 'mac': mac, 'node2': nei.n9.id, 'port2': nei.port.port_id, 'pc-id': nei.port.pc_id})
                else:
                    wires_cfg.append({'node1': node1, 'port1': port1, 'mac': mac, 'node2': None,      'port2': None,             'pc-id': None})

        for n9 in pod.vim_tors + pod.vim_cat:
            for nei in n9.neighbours_cdp:
                if nei.port_id == 'mgmt0':
                    wires_cfg.append({'node1': n9.id, 'port1': nei.port_id, 'mac': 'unknown', 'node2': pod.oob[0].id, 'port2': nei.peer_port_id, 'pc-id': nei.pc_id})
                else:
                    s = filter(lambda y: y.get_oob()[0] == nei.ipv4, pod.tor + pod.vim_tors)
                    if s:
                        sw = s[0]
                        wires_cfg.append({'node1': n9.id, 'port1': nei.port_id, 'mac': 'unknown', 'node2': sw.id, 'port2': nei.peer_port_id, 'pc-id': nei.pc_id})

                        # global_vlans = filter(lambda net: net.is_via_tor(), lab.get_all_nets().values())
                    # a = n9.n9_cmd('sh spanning-tree vlan {}'.format(global_vlans[0].get_vlan_id()))
            # uplink_candidate_pc_id = [x['if_index'] for x in a.values()[0][u'TABLE_port'][u'ROW_port'] if x['role'] == 'root'][0]
            # uplink_candidate_port_ids = [x['port'] for x in r['ports'][uplink_candidate_pc_id]['ports']]

        return sorted(wires_cfg, key=lambda e: e['node1'])

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

    def process_mercury_nodes(self, mercury_cfg):
        cimc_username = mercury_cfg['CIMC-COMMON']['cimc_username']
        cimc_password = mercury_cfg['CIMC-COMMON']['cimc_password']
        ssh_username = mercury_cfg['COBBLER']['admin_username']
        ssh_password = 'cisco123'

        nodes = [{'node': 'mgm', 'role': 'CimcDirector', 'oob-ip': mercury_cfg['TESTING_MGMT_NODE_CIMC_IP'], 'oob-username': mercury_cfg['TESTING_MGMT_CIMC_USERNAME'], 'oob-password': mercury_cfg['TESTING_MGMT_CIMC_PASSWORD'],
                  'ssh-username': ssh_username, 'ssh-password': ssh_password, 'proxy': None,
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

                    nodes.append({'node': node_id, 'role': sqe_role_id, 'oob-ip': oob_ip, 'oob-username': oob_username, 'oob-password': oob_password, 'ssh-username': ssh_username, 'ssh-password': ssh_password,
                                  'proxy': 'mgm', 'nics': nics})

                    if mercury_role_id == 'vts':
                        vtc_nics = [{'nic-id': 'a', 'ip': mercury_cfg['VTS_PARAMETERS']['VTS_VTC_API_IPS'][i-1], 'is-ssh': True},
                                    {'nic-id': 'm', 'ip': mercury_cfg['VTS_PARAMETERS']['VTS_VTC_MGMT_IPS'][i-1], 'is-ssh': False}]
                        xrvr_nics = [{'nic-id': 'm', 'ip': mercury_cfg['VTS_PARAMETERS']['VTS_XRNC_MGMT_IPS'][i-1], 'is-ssh': True},
                                     {'nic-id': 't', 'ip': mercury_cfg['VTS_PARAMETERS']['VTS_XRNC_TENANT_IPS'][i-1], 'is-ssh': False}]

                        virtuals.append({'node': 'vtc' + str(i), 'role': 'vtc', 'oob-ip': None, 'oob-username': oob_username, 'oob-password': mercury_cfg['VTS_PARAMETERS']['VTS_PASSWORD'],
                                         'ssh-username': 'admin', 'ssh-password': ssh_password,
                                         'virtual-on': node_id, 'vip_a': mercury_cfg['VTS_PARAMETERS']['VTS_VTC_API_VIP'], 'vip_m': mercury_cfg['VTS_PARAMETERS']['VTS_NCS_IP'], 'proxy': None, 'nics': vtc_nics})
                        virtuals.append({'node': 'xrvr' + str(i), 'role': 'xrvr', 'oob-ip': None, 'oob-username': oob_username, 'oob-password': oob_password, 'ssh-username': ssh_username, 'ssh-password': ssh_password,
                                         'virtual-on': node_id, 'proxy': 'mgm', 'nics': xrvr_nics})
                except KeyError as ex:
                    raise KeyError('{}: no {}'.format(node_id, ex))
        return nodes, virtuals

    @staticmethod
    def save_self_config(pod):
        from lab.nodes.virtual_server import VirtualServer
        from lab.nodes.lab_server import LabServer
        from lab.nodes.vtc import Vtc

        virtual = 'V'
        switch = 'S'
        others = 'O'

        def net_yaml_body(net):
            return '{{net-id: {:3}, vlan: {:4}, cidr: {:19}, is-via-tor: {:5}, should-be: {}}}'.format(net.get_net_id(), net.get_vlan_id(), net.get_cidr(), 'True' if net.is_via_tor() else 'False', net.get_roles())

        def nic_yaml_body(nic):
            return '{{nic-id: {:3}, ip: {:20}, is-ssh: {:6} }}'.format(nic.get_nic_id(), nic.get_ip_and_mask()[0], nic.is_ssh())

        def node_yaml_body(node, tp):
            n_id = node.id
            pn_id = node.proxy.id if node.proxy is not None else None
            role = node.role
            oob_ip, oob_u, oob_p = node.get_oob()
            if tp == switch:
                ssh_u, ssh_p = oob_u, oob_p
            else:
                ssh_u, ssh_p = node.get_ssh_u_p()
            a = ' {{node: {:5}, role: {:10}, proxy: {:5}, ssh-username: {:15}, ssh-password: {:9}, oob-ip: {:15},  oob-username: {:15}, oob-password: {:9}'.format(n_id, role, pn_id, ssh_u, ssh_p, oob_ip, oob_u, oob_p)
            if tp == virtual:
                a += ', virtual-on: {:5}'.format(node.hard.id)
            if type(node) is Vtc:
                vip_a, vip_m = node.get_vtc_vips()
                a += ', vip_a: {:15}, vip_m: {:15}'.format(vip_a, vip_m)
            if tp != switch:
                nics = ',\n              '.join(map(lambda y: nic_yaml_body(y), node.get_nics().values()))
                a += ',\n      nics: [ {}\n      ]\n'.format(nics)
            a += ' }'
            return a

        def wire_yaml_body(wire):
            a1 = 'pc-id: {:>15}, '.format(wire.pc_id)
            a2 = 'node1: {:>5}, port1: {:>45}, mac: "{:17}", '.format(wire.n1, wire.port_id1, wire.mac)
            a3 = 'node2: {:>5}, port2: {:>20}'.format(wire.n2, wire.port_id2)
            return '{' + a1 + a2 + a3 + ' }'

        with open('{}.yaml'.format(pod), 'w') as f:
            f.write('name: {} # any string to be used on logging\n'.format(pod))
            f.write('type: {} # supported types: {}\n'.format(pod.type, ' '.join(pod.SUPPORTED_TYPES)))
            f.write('description-url: "{}"\n'.format(pod))
            f.write('\n')
            f.write('# special creds to be used by OS neutron services\n')
            f.write('special-creds: {{neutron_username: {}, neutron_password: {}}}\n'.format(pod.neutron_username, pod.neutron_password))
            f.write('\n')

            f.write('specials: [\n')
            special_bodies = [node_yaml_body(node=x, tp=switch) for x in pod.oob + pod.tor]
            f.write(',\n'.join(special_bodies))
            f.write('\n]\n\n')

            f.write('networks: [\n')
            net_bodies = [net_yaml_body(net=x) for x in pod.networks.values()]
            f.write(',\n'.join(net_bodies))
            f.write('\n]\n\n')

            f.write('switches: [\n')
            switch_bodies = [node_yaml_body(node=x, tp=switch) for x in pod.vim_tors + pod.vim_cat]
            f.write(',\n'.join(switch_bodies))
            f.write('\n]\n\n')

            f.write('nodes: [\n')
            node_bodies = [node_yaml_body(node=x, tp=others) for x in pod.nodes.values() if isinstance(x, LabServer) and not isinstance(x, VirtualServer)]
            f.write(',\n\n'.join(node_bodies))
            f.write('\n]\n\n')

            f.write('virtuals: [\n')
            node_bodies = [node_yaml_body(node=x, tp=virtual) for x in pod.nodes.values() if isinstance(x, VirtualServer)]
            f.write(',\n\n'.join(node_bodies))
            f.write('\n]\n\n')

            f.write('wires: [\n')

            n1_id = ''
            for w in pod.wires:
                if w.n1.id != n1_id:
                    n1_id = w.n1.id
                    f.write('\n')
                f.write(wire_yaml_body(wire=w) + ',\n')
            f.write('\n]\n')

            if pod.setup_data:
                f.write('\nsetup-data: {}'.format(pod.setup_data))


if __name__ == '__main__':
    c = Configurator()
