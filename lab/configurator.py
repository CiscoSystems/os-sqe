from lab.with_config import WithConfig
from lab.with_log import WithLogMixIn


class LabConfigurator(WithConfig, WithLogMixIn):
    def sample_config(self):
        pass

    def __init__(self):
        super(LabConfigurator, self).__init__()
        self.execute()

    def __repr__(self):
        return u'LAB CONFIGURATOR'

    @staticmethod
    def get_ip(msg, ip):
        from fabric.operations import prompt
        import validators

        while True:
            ip4 = prompt(text=msg + ' (default is {})> '.format(ip)) or ip
            if validators.ipv4(ip4):
                return ip4
            else:
                continue

    def process_connections(self, lab):
        def normalize_mac(m):
            return ':'.join([m[0:2], m[2:4], m[5:7], m[7:9], m[10:12], m[12:14]])

        global_vlans = filter(lambda net: net.is_via_tor(), lab.get_all_nets().values())

        mac_vs_node = {}
        for cimc in lab.get_cimc_servers():
            self.log('Reading {} CIMC NICs'.format(cimc))
            r = cimc.cimc_list_pci_nic_ports()
            for port_id, mac in r.items():
                mac_vs_node[mac] = {'node': cimc, 'port-id': port_id}

        wires_cfg = []
        for n9 in lab.get_n9k():
            r = n9.n9_show_all()

            a = n9.n9_cmd('sh spanning-tree vlan {}'.format(global_vlans[0].get_vlan_id()))
            uplink_candidate_pc_id = [x['if_index'] for x in a.values()[0][u'TABLE_port'][u'ROW_port'] if x['role'] == 'root'][0]
            uplink_candidate_port_ids = [x['port'] for x in r['ports'][uplink_candidate_pc_id]['ports']]
            for cdp in r['cdp']:
                n9_port_id = cdp.get('intf_id')
                n9_mac = 'unknown'
                peer_port_id = cdp.get('port_id')
                peer_ip = cdp.get('v4mgmtaddr')
                peer_mac = 'unknown'
                n9_pc_id = 'unknown'

                if n9_port_id == 'mgmt0':
                    peer = lab.get_oob()
                    peer.set_oob_creds(ip=peer_ip, username='openstack-read', password='CTO1234!')
                elif n9_port_id in uplink_candidate_port_ids:
                    peer = lab.get_tor()
                    peer.set_oob_creds(ip=peer_ip, username='openstack-read', password='CTO1234!')
                else:  # assuming here that all others are peer link
                    peer = [x for x in lab.get_n9k() if x.get_oob()[0] == peer_ip]
                    if len(peer) != 1:
                        continue  # assume that this device is not a part of the lab
                    peer = peer[0]
                wires_cfg.append({'from-node-id': n9.get_node_id(), 'from-port-id': n9_port_id, 'from-mac': n9_mac, 'to-node-id': peer.get_node_id(), 'to-port-id': peer_port_id, 'to-mac': peer_mac, 'pc-id': n9_pc_id})

            for lldp in r['lldp']['TABLE_nbor_detail']['ROW_nbor_detail']:
                cimc_mac = normalize_mac(lldp['port_id'])
                if cimc_mac in mac_vs_node:
                    n9_port_id = lldp.get('l_port_id').replace('Eth', 'Ethernet')
                    n9_mac = 'unknown'
                    n9_pc_id_lst = [p_id for p_id, p_d in r['ports'].items() if 'port-channel' in p_id and n9_port_id in [x['port']for x in p_d['ports']]]
                    n9_pc_id = n9_pc_id_lst[0] if len(n9_pc_id_lst) else 'unknown'
                    cimc_node = mac_vs_node[cimc_mac]['node']
                    cimc_port_id = mac_vs_node[cimc_mac]['port-id']
                    wires_cfg.append({'from-node-id': cimc_node.get_node_id(), 'from-port-id': cimc_port_id, 'from-mac': cimc_mac, 'to-node-id': n9.get_node_id(), 'to-port-id': n9_port_id, 'to-mac': n9_mac, 'pc-id': n9_pc_id})
        return sorted(wires_cfg, key=lambda e: e['from-node-id'])

    def execute(self):
        import os

        lab_name = 'c35bottom'
        lab_dir_in_mercury_repo = os.path.expanduser('~/repo/mercury/testbeds/' + lab_name + '/')

        mercury_yaml = lab_dir_in_mercury_repo + 'setup_data.vpp.yaml'

        if os.path.isfile(mercury_yaml):
            self.process_mercury_setup_data(yaml_path=mercury_yaml)
        else:
            self.log('not yet implemented way to configure')

    def process_mercury_setup_data(self, yaml_path):
        from lab.laboratory import Laboratory

        mercury_cfg = self.read_config_from_file(yaml_path)

        net_name_translator = {'api': 'a', 'management': 'mx', 'tenant': 't', 'external': 'e', 'provider': 'p', 'storage': 's'}
        should_be = {'a':  ['director-n9', 'control-n9', 'vtc'],
                     'mx': ['director-n9', 'control-n9', 'compute-n9', 'ceph-n9', 'vtc', 'xrvr', 'vts-host-n9'],
                     't':  ['compute-n9', 'xrvr', 'vts-host-n9'],
                     's':  ['control-n9', 'compute-n9', 'ceph-n9'],
                     'e':  ['control-n9'],
                     'p':  ['compute-n9']}

        nets = list()
        for net_info in mercury_cfg['NETWORKING']['networks']:
            cidr = net_info.get('subnet')
            if not cidr:
                continue
            net_name = net_name_translator[net_info['segments'][0]]

            if net_name == 'mx':
                mac_pattern = '99'
            elif net_name == 't':
                mac_pattern = 'cc'
            elif net_name == 's':
                mac_pattern = 'dd'
            elif net_name == 'a':
                mac_pattern = 'aa'
            elif net_name == 'e':
                mac_pattern = 'ee'
            elif net_name == 'p':
                mac_pattern = 'ff'
            else:
                raise ValueError('unxepected network segment found')
            vlan_id = net_info['vlan_id']
            nets.append({'net-id': net_name, 'vlan': vlan_id, 'mac-pattern': mac_pattern, 'cidr': cidr, 'should-be': should_be[net_name], 'is-via-tor': net_name in ['a']})

        cimc_username = mercury_cfg['CIMC-COMMON']['cimc_username']
        cimc_password = mercury_cfg['CIMC-COMMON']['cimc_password']
        ssh_username = mercury_cfg['COBBLER']['admin_username']
        ssh_password = 'cisco123'

        switches = [{'node-id': 'oob', 'role': 'oob', 'oob-ip': '???1', 'oob-username': '????', 'oob-password': '?????', 'ssh-username': 'None', 'ssh-password': 'None', 'proxy-id': None},
                    {'node-id': 'tor', 'role': 'tor', 'oob-ip': '???2', 'oob-username': '????', 'oob-password': '?????', 'ssh-username': 'None', 'ssh-password': 'None', 'proxy-id': None}]

        for i, sw in enumerate(mercury_cfg['TORSWITCHINFO']['SWITCHDETAILS'], start=1):
            switches.append({'node-id': 'n9' + str(i), 'role': 'n9', 'oob-ip': sw['ssh_ip'], 'oob-username': sw['username'], 'oob-password': sw['password'], 'ssh-username': 'None', 'ssh-password': 'None', 'proxy-id': None})

        nodes = [{'node-id': 'mgm', 'role': 'director-n9', 'oob-ip': mercury_cfg['TESTING_MGMT_NODE_CIMC_IP'], 'oob-username': mercury_cfg['TESTING_MGMT_CIMC_USERNAME'], 'oob-password': mercury_cfg['TESTING_MGMT_CIMC_PASSWORD'],
                  'ssh-username': ssh_username, 'ssh-password': ssh_password, 'proxy-id': None,
                  'nics': [{'nic-id': 'a', 'ip': mercury_cfg['TESTING_MGMT_NODE_API_IP'].split('/')[0], 'is-ssh': True},
                           {'nic-id': 'mx', 'ip': mercury_cfg['TESTING_MGMT_NODE_MGMT_IP'].split('/')[0], 'is-ssh': False}]}]

        for role, node_ids in mercury_cfg['ROLES'].items():
            for node_id in node_ids:
                role_sqe = role + '-n9'
                try:
                    srv_cfg = mercury_cfg['SERVERS'][node_id]
                    oob_ip = srv_cfg['cimc_info']['cimc_ip']
                    oob_username = srv_cfg['cimc_info'].get('cimc_username', cimc_username)
                    oob_password = srv_cfg['cimc_info'].get('cimc_password', cimc_password)

                    ips = {net_name_translator[key.replace('_ip', '')]: val for key, val in srv_cfg.items() if '_ip' in key}

                    nics = [{'nic-id': net_id, 'ip': ip, 'is-ssh': net_id == 'mx'} for net_id, ip in ips.items()]
                    nodes.append({'node-id': node_id, 'role': role_sqe, 'oob-ip': oob_ip, 'oob-username': oob_username, 'oob-password': oob_password, 'ssh-username': ssh_username, 'ssh-password': ssh_password, 'nics': nics,
                                  'proxy-id': 'mgm'})
                except KeyError as ex:
                    raise KeyError('{}: no {}'.format(node_id, ex))

        sqe_cfg = {'lab-name': yaml_path.split('/')[-2], 'lab-id': 99, 'lab-type': 'MERCURY-' + mercury_cfg['MECHANISM_DRIVERS'].upper(), 'dns': ['171.70.168.183'], 'ntp': ['171.68.38.66'],
                   'special-creds': {'neutron_username': 'admin', 'neutron_password': 'new123'},
                   'networks': nets, 'switches': switches, 'nodes': nodes, 'wires': []}
        lab = Laboratory(sqe_cfg)
        sqe_cfg['wires'] = self.process_connections(lab=lab)
        sqe_cfg['switches'][0]['oob-ip'] = lab.get_oob().get_oob()[0]
        sqe_cfg['switches'][1]['oob-ip'] = lab.get_tor().get_oob()[0]

        lab = Laboratory(sqe_cfg)

        self.save_lab_config(lab=lab)

    def save_lab_config(self, lab):
        saved_config_path = self.get_artifact_file_path('saved_{}.yaml'.format(lab._lab_name))
        with self.open_artifact(name=saved_config_path, mode='w') as f:
            f.write('lab-id: {} # integer in ranage (0,99). supposed to be unique in current L2 domain since used in MAC pools\n'.format(lab.get_id()))
            f.write('lab-name: {} # any string to be used on logging\n'.format(lab))
            f.write('lab-type: {} # supported types: {}\n'.format(lab.get_type(), ' '.join(lab.SUPPORTED_TYPES)))
            f.write('description-url: "{}"\n'.format(lab))
            f.write('\n')
            f.write('dns: {}\n'.format(lab.get_dns()))
            f.write('ntp: {}\n'.format(lab.get_ntp()))
            f.write('\n')
            f.write('# special creds to be used by OS neutron services\n')
            f.write('special-creds: {{neutron_username: {}, neutron_password: {}}}\n'.format(lab._neutron_username, lab._neutron_password))
            f.write('\n')

            f.write('networks: [\n')
            net_bodies = [net.get_yaml_body() for net in lab.get_all_nets().values()]
            f.write(',\n'.join(net_bodies))
            f.write('\n]\n\n')

            f.write('nodes: [\n')
            node_bodies = [node.get_yaml_body() for node in lab.get_switches()]
            f.write(',\n'.join(node_bodies))
            f.write('\n]\n\n')

            f.write('nodes: [\n')
            node_bodies = [node.get_yaml_body() for node in lab.get_servers_with_nics()]
            f.write(',\n\n'.join(node_bodies))
            f.write('\n]\n\n')

            f.write('wires: [\n')
            wires_body = [wire.get_yaml_body() for wire in lab.get_all_wires()]
            f.write(',\n'.join(wires_body))
            f.write('\n]\n')
