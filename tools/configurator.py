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
        'g7-2': [{'id': 'term', 'role': 'terminal', 'oob-ip': '172.31.229.55', 'oob-username': 'openstack-read'},
                 {'id': 'pxe', 'role': 'pxe', 'oob-ip': '172.31.230.170', 'oob-username': 'openstack-read'}]
    }

    def sample_config(self):
        pass

    def __init__(self):
        from lab.network import Network
        from lab.laboratory import Laboratory

        super(Configurator, self).__init__()

        self._nets = {'api':        Network(net_id='a', cidr='10.10.10.0/32', vlan=9999, is_via_tor=True,  pod='', roles_must_present=['CimcDirector', 'CimcController', 'Vtc', 'VtsHost']),
                      'management': Network(net_id='m', cidr='11.11.11.0/24', vlan=2011, is_via_tor=False, pod='', roles_must_present=['CimcDirector', 'CimcController', 'CimcCompute', 'CimcCeph', 'CimcCompute',
                                                                                                                                       'Vtc', 'Xrvr', 'VtsHost']),
                      'tenant':     Network(net_id='t', cidr='22.22.22.0/24', vlan=2022, is_via_tor=False, pod='', roles_must_present=['CimcCompute', 'Xrvr', 'VtsHost']),
                      'storage':    Network(net_id='s', cidr='33.33.33.0/24', vlan=2033, is_via_tor=False, pod='', roles_must_present=['CimcController', 'CimcCompute', 'CimcCeph']),
                      'external':   Network(net_id='e', cidr='44.44.44.0/24', vlan=2044, is_via_tor=False, pod='', roles_must_present=['CimcController']),
                      'provider':   Network(net_id='p', cidr='55.55.55.0/24', vlan=2055, is_via_tor=False, pod='', roles_must_present=['CimcCompute'])}
        self.pod = Laboratory()

    def create_from_remote(self, ip):
        import yaml
        from lab.server import Server

        s = Server(ip=ip, username='root', password='cisco123')
        ans = s.exe(command='cat /root/openstack-configs/setup_data.yaml', is_warn_only=True)
        if 'No such file or directory' in ans:
            raise RuntimeError('mgm node {} does not have setup_data.yaml'.format(ip))

        setup_data = yaml.load(ans)
        return self.create_from_setup_data(setup_data=setup_data)

    def create_from_setup_data(self, setup_data):
        self.pod.setup_data = setup_data
        self.pod.name = setup_data['TESTING_TESTBED_NAME']

        self.process_mercury_nets()
        self.process_switches()
        self.process_mercury_nodes()
        self.process_connections()
        self.pod.validate_config()
        self.save_self_config(pod=self.pod)
        return self.pod

    def process_switches(self):
        from lab.nodes.n9.vim_tor import VimTor
        from lab.wire import Wire

        pod_name = self.pod.setup_data['TESTING_TESTBED_NAME']
        catalyst = {'g7-2': '10.23.223.176'}

        switches = []
        username, password = None, None
        for sw in self.pod.setup_data['TORSWITCHINFO']['SWITCHDETAILS']:
            username, password = sw['username'], sw['password']
            switches.append({'id': 'n' + sw['hostname'][-1].lower(), 'role': 'VimTor', 'oob-ip': sw['ssh_ip'], 'oob-username': username, 'oob-password': password})

        if pod_name in catalyst:
            switches.append({'id': 'nc', 'role': 'VimCat', 'oob-ip': catalyst[pod_name], 'oob-username': username, 'oob-password': password})

        tors = VimTor.add_nodes(pod=None, nodes_cfg=switches)

        specials = {}
        wires_cfg = []
        for n9 in tors.values():
            for nei in n9.neighbours_cdp:
                node2_id = nei.ipv4.split('.')[-1]
                if nei.port_id == 'mgmt0':
                    specials[nei.ipv4] = {'id': node2_id, 'role': 'Oob', 'oob-ip': nei.ipv4, 'oob-username': 'XXXXXX', 'oob-password': password}
                else:
                    s = filter(lambda y: y.oob_ip == nei.ipv4, tors.values())
                    if s:
                        node2_id = s[0].id
                    else:  # this is unknown connection, one of them is connection to tor
                        specials[nei.ipv4] = {'id': node2_id, 'role': 'Tor', 'oob-ip': nei.ipv4, 'oob-username': 'XXXXXX', 'oob-password': password}
                wires_cfg.append({'node1': n9.id, 'port1': nei.port_id, 'mac': 'unknown', 'node2': node2_id, 'port2': nei.peer_port_id, 'pc-id': nei.pc_id})

        for i, x in enumerate(Configurator.KNOWN_SPECIALS.get(pod_name, [])):
            x['oob-password'] = password
            specials[i] = x

        self.pod.nodes.update(tors)
        self.pod.nodes.update(VimTor.add_nodes(pod=self.pod, nodes_cfg=specials.values()))
        self.pod.wires.extend(Wire.add_wires(pod=self.pod, wires_cfg=wires_cfg))

    def create_from_local_mercury_repo(self):
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
        setup_data = self.read_config_from_file(os.path.join(pod_dir, yaml_name))
        return self.create_from_setup_data(setup_data=setup_data)

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

    def process_connections(self):
        import yaml
        from lab.wire import Wire

        cimc_info_yaml = Configurator.get_artifact_file_path('{}-cimc-info.yaml'.format(self.pod))
        try:
            cimc_info_dic = Configurator.read_config_from_file(config_path=cimc_info_yaml)
        except ValueError:
            cimc_info_dic = {}
            for cimc in self.pod.cimc_servers:
                cimc_info_dic[cimc.id] = cimc.cimc_list_all_nics()  # returns dic of {port_id: mac}
            with Configurator.open_artifact(name=cimc_info_yaml, mode='w') as f:
                yaml.dump(cimc_info_dic, f)

        wires_cfg = []
        for node1, d in cimc_info_dic.items():
            for port1, mac in d.items():
                neis = [x.find_neighbour_with_mac(mac=mac, cimc_port_id=port1) for x in self.pod.vim_tors + self.pod.vim_cat]
                neis = filter(lambda n: n is not None, neis)
                if neis:
                    assert len(neis) == 1, 'More then 1 switch is found connected to the {} {}'.format(node1, port1)
                    nei = neis[0]
                    wires_cfg.append({'node1': node1, 'port1': port1, 'mac': mac, 'node2': nei.n9.id, 'port2': nei.port.port_id, 'pc-id': nei.port.pc_id})
                else:
                    wires_cfg.append({'node1': node1, 'port1': port1, 'mac': mac, 'node2': None,      'port2': None,             'pc-id': None})

        self.pod.wires.extend(Wire.add_wires(pod=self.pod, wires_cfg=wires_cfg))

    def process_mercury_nets(self):
        from lab.network import Network
        from netaddr import IPNetwork

        for mercury_net_id, net in self._nets.items():
            net_mercury_cfg = filter(lambda k: k['segments'][0] == mercury_net_id, self.pod.setup_data['NETWORKING']['networks'])
            if net_mercury_cfg:
                cidr = net_mercury_cfg[0].get('subnet')
                vlan_id = net_mercury_cfg[0]['vlan_id']
                net.vlan = vlan_id
                if cidr:
                    net.net = IPNetwork(cidr)
                    net.is_via_tor = cidr[:2] not in ['11', '22', '33', '44', '55']
                elif vlan_id in self.KNOWN_EXT_VLANS:
                    net.net = IPNetwork(self.KNOWN_EXT_VLANS[vlan_id])

        self.pod.networks.update(Network.add_networks(pod=self.pod, nets_cfg=[{'id': x.id, 'vlan': x.vlan, 'cidr': x.net.cidr, 'roles': x.roles_must_present, 'is-via-tor': x.is_via_tor} for x in self._nets.values()]))

    def process_mercury_nodes(self):
        from lab.nodes import LabNode
        from lab.nodes.virtual_server import VirtualServer

        cimc_username = self.pod.setup_data['CIMC-COMMON']['cimc_username']
        cimc_password = self.pod.setup_data['CIMC-COMMON']['cimc_password']
        ssh_username = self.pod.setup_data['COBBLER']['admin_username']
        ssh_password = None

        nodes = [{'id': 'mgm', 'role': 'CimcDirector',
                  'oob-ip': self.pod.setup_data['TESTING_MGMT_NODE_CIMC_IP'], 'oob-username': self.pod.setup_data['TESTING_MGMT_CIMC_USERNAME'], 'oob-password': self.pod.setup_data['TESTING_MGMT_CIMC_PASSWORD'],
                  'ssh-username': ssh_username, 'ssh-password': ssh_password, 'proxy': None,
                  'nics': [{'id': 'a', 'ip': self.pod.setup_data['TESTING_MGMT_NODE_API_IP'].split('/')[0], 'is-ssh': True},
                           {'id': 'm', 'ip': self.pod.setup_data['TESTING_MGMT_NODE_MGMT_IP'].split('/')[0], 'is-ssh': False}]}]

        virtuals = []

        for mercury_role_id, mercury_node_ids in self.pod.setup_data['ROLES'].items():
            sqe_role_id = {'control': 'CimcController', 'compute': 'CimcCompute', 'block_storage': 'CimcCeph', 'vts': 'VtsHost'}[mercury_role_id]

            nets_for_this_role = {mercury_net_id: net for mercury_net_id, net in self._nets.items() if sqe_role_id in net.roles_must_present}

            for i, node_id in enumerate(mercury_node_ids, start=1):
                try:
                    mercury_srv_cfg = self.pod.setup_data['SERVERS'][node_id]
                    oob_ip = mercury_srv_cfg['cimc_info']['cimc_ip']
                    oob_username = mercury_srv_cfg['cimc_info'].get('cimc_username', cimc_username)
                    oob_password = mercury_srv_cfg['cimc_info'].get('cimc_password', cimc_password)

                    nics = []
                    for mercury_net_id, net in nets_for_this_role.items():
                        ip_base = {'control': 10, 'compute': 20, 'ceph': 30, 'vts': 40}[mercury_role_id] if net.is_via_tor else 4
                        ip = mercury_srv_cfg.get(mercury_net_id + '_ip', str(net.get_ip_for_index(ip_base + i)))
                        nics.append({'id': mercury_net_id[0], 'ip': ip, 'is-ssh': mercury_net_id == 'management'})

                    nodes.append({'id': node_id, 'role': sqe_role_id, 'oob-ip': oob_ip, 'oob-username': oob_username, 'oob-password': oob_password, 'ssh-username': ssh_username,
                                  'proxy': 'mgm', 'nics': nics})

                    if mercury_role_id == 'vts':
                        vtc_nics = [{'id': 'a', 'ip': self.pod.setup_data['VTS_PARAMETERS']['VTS_VTC_API_IPS'][i-1], 'is-ssh': True},
                                    {'id': 'm', 'ip': self.pod.setup_data['VTS_PARAMETERS']['VTS_VTC_MGMT_IPS'][i-1], 'is-ssh': False}]
                        xrvr_nics = [{'id': 'm', 'ip': self.pod.setup_data['VTS_PARAMETERS']['VTS_XRNC_MGMT_IPS'][i-1], 'is-ssh': True},
                                     {'id': 't', 'ip': self.pod.setup_data['VTS_PARAMETERS']['VTS_XRNC_TENANT_IPS'][i-1], 'is-ssh': False}]

                        virtuals.append({'id': 'vtc' + str(i), 'role': 'vtc', 'oob-ip': None, 'oob-username': oob_username, 'oob-password': self.pod.setup_data['VTS_PARAMETERS']['VTS_PASSWORD'],
                                         'ssh-username': 'admin', 'ssh-password': ssh_password,
                                         'virtual-on': node_id, 'vip_a': self.pod.setup_data['VTS_PARAMETERS']['VTS_VTC_API_VIP'], 'vip_m': self.pod.setup_data['VTS_PARAMETERS']['VTS_NCS_IP'], 'proxy': None, 'nics': vtc_nics})
                        virtuals.append({'id': 'xrvr' + str(i), 'role': 'xrvr', 'oob-ip': None, 'oob-username': oob_username, 'oob-password': oob_password, 'ssh-username': ssh_username, 'ssh-password': ssh_password,
                                         'virtual-on': node_id, 'proxy': 'mgm', 'nics': xrvr_nics})
                except KeyError as ex:
                    raise KeyError('{}: no {}'.format(node_id, ex))

        self.pod.nodes.update(LabNode.add_nodes(pod=self.pod, nodes_cfg=nodes))
        self.pod.nodes.update(VirtualServer.add_nodes(pod=self.pod, nodes_cfg=virtuals))

    @staticmethod
    def save_self_config(pod):
        from lab.nodes.virtual_server import VirtualServer
        from lab.nodes.lab_server import LabServer
        from lab.nodes.vtc import Vtc

        virtual = 'V'
        switch = 'S'
        others = 'O'

        def net_yaml_body(net):
            return '{{id: {:3}, vlan: {:4}, cidr: {:19}, is-via-tor: {:5}, roles: {}}}'.format(net.id, net.vlan, net.net.cidr, 'True' if net.is_via_tor else 'False', net.roles_must_present)

        def nic_yaml_body(nic):
            return '{{id: {:3}, ip: {:20}, is-ssh: {:6} }}'.format(nic.id, nic.ip, nic.is_ssh)

        def node_yaml_body(node, tp):
            pn_id = node.proxy.id if node.proxy is not None else None
            a = ' {{id: {:8}, role: {:10}, proxy: {:5}, oob-ip: {:15}, oob-username: {:15}, oob-password: {:9}'.format(node.id, node.role, pn_id, node.oob_ip, node.oob_username, node.oob_password)
            if tp == virtual:
                a += ', virtual-on: {:5}'.format(node.hard.id)
            if type(node) is Vtc:
                vip_a, vip_m = node.get_vtc_vips()
                a += ', vip_a: {:15}, vip_m: {:15}'.format(vip_a, vip_m)
            if tp != switch:
                nics = ',\n              '.join(map(lambda y: nic_yaml_body(y), node.nics.values()))
                a += ',\n      nics: [ {}\n      ]\n'.format(nics)
            a += ' }'
            return a

        def wire_yaml_body(wire):
            a1 = 'pc-id: {:>15}, '.format(wire.pc_id)
            a2 = 'node1: {:>5}, port1: {:>45}, mac: "{:17}", '.format(wire.n1, wire.port_id1, wire.mac)
            a3 = 'node2: {:>5}, port2: {:>20}'.format(wire.n2, wire.port_id2)
            return '{' + a1 + a2 + a3 + ' }'

        with Configurator.open_artifact('{}.yaml'.format(pod), 'w') as f:
            f.write('name: {} # any string to be used on logging\n'.format(pod))
            f.write('description-url: "{}"\n'.format(pod))
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
            node_bodies = sorted([node_yaml_body(node=x, tp=others) for x in pod.nodes.values() if isinstance(x, LabServer) and not isinstance(x, VirtualServer)])
            f.write(',\n\n'.join(node_bodies))
            f.write('\n]\n\n')

            f.write('virtuals: [\n')
            node_bodies = [node_yaml_body(node=x, tp=virtual) for x in pod.nodes.values() if isinstance(x, VirtualServer)]
            f.write(',\n\n'.join(node_bodies))
            f.write('\n]\n\n')

            f.write('wires: [\n')

            n1_id = ''
            for w in sorted(pod.wires, key=lambda e: e.n1.id + e.port_id1):
                if w.n1.id != n1_id:
                    n1_id = w.n1.id
                    f.write('\n')
                f.write(wire_yaml_body(wire=w) + ',\n')
            f.write('\n]\n')

            if pod.setup_data:
                f.write('\nsetup-data: {}'.format(pod.setup_data))

if __name__ == '__main__':
    from lab.laboratory import Laboratory

    c = Configurator()
    pod = c.create_from_local_mercury_repo()
    c.save_self_config(pod=pod)
    Laboratory.create_from_path(cfg_path=Laboratory.get_artifact_file_path(pod.name + '.yaml'))
