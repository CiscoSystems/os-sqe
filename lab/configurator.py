from lab.with_config import WithConfig
from lab.with_log import WithLogMixIn


class LabConfigurator(WithConfig, WithLogMixIn):
    def sample_config(self):
        pass

    def __init__(self, lab_name):
        super(LabConfigurator, self).__init__()
        self.execute(lab_name=lab_name)

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

    def process_mgmt_node(self, bld_ip):
        from fabric.operations import prompt
        import validators
        from lab.server import Server

        bld_ip = self.get_ip('Specify your mgmt node IP', ip=bld_ip)
        bld_username = 'root'
        bld_password = 'cisco123'

        bld_username = prompt(text='Enter username for N9K at {} (default is {}): '.format(bld_ip, bld_username)) or bld_username
        bld_password = prompt(text='Enter password for N9K at {} (default is {}): '.format(bld_ip, bld_password)) or bld_password
        bld = Server(ip=bld_ip, username=bld_username, password=bld_password)

        # bld.exe('cat /etc/hosts')
        self._mac_host = {x: 'bld' for x in bld.r_list_ip_info().keys() if validators.mac_address(x)}

    def process_n9(self, n9_ip):
        from fabric.operations import prompt
        from lab.nodes.n9k import Nexus
        from lab.nodes.tor import Oob, Tor
        from lab.wire import Wire
        from lab.nodes.cimc_server import CimcServer

        n91_ip = self.get_ip('Specify one of your N9K IP', n9_ip)
        n9k_username = 'admin'
        n9k_password = 'CTO1234!'

        n9_username = prompt(text='Enter username for N9K at {} (default is {}): '.format(n91_ip, n9k_username)) or n9k_username
        n9_password = prompt(text='Enter password for N9K at {} (default is {}): '.format(n91_ip, n9k_password)) or n9k_password

        n91 = Nexus(node_id='n91', role=Nexus.ROLE, lab='fake-lab')
        n91.set_oob_creds(ip=n91_ip, username=n9k_username, password=n9k_password)

        self.log('Step 1: we try to find peer info:')
        #    nodes = OrderedDict()
        nodes = {'tor': None, 'oob': None, 'n9k': [n91], 'cimc': [], 'fi': []}
        # for node in self.get_nodes_by_class(CimcServer):
        #     nodes[node.get_id()] = node.cimc_list_vnics()
        #     nodes[node.get_id()] = node.cimc_list_lom_ports()
        #     node.cimc_get_mgmt_nic()

        # peer_links = []
        n92 = None
        cdps = n91.n9_show_cdp_neighbor()
        # ports = n91.n9_show_ports()
        # pc = n91.n9_show_port_channels()
        # vpc = n91.n9_show_vpc()

        for cdp in cdps:
            own_port_id = cdp.get('intf_id')
            peer_port_id = cdp.get('port_id')

            if own_port_id == 'mgmt0':
                oob = Oob(node_id='oob', role=Oob.ROLE, lab='fake-lab')
                oob.set_oob_creds(ip=cdp.get('v4mgmtaddr'), username='?????', password='?????')
                Wire(node_n=oob, port_n=peer_port_id, node_s=n91, port_s=own_port_id, port_channel=None, vlans=[], mac=None)
                nodes['oob'] = oob
            elif 'TOR' in cdp.get('sysname', ''):
                tor = Tor(node_id='tor', role=Tor.ROLE, lab='fake-lab')
                tor.set_oob_creds(ip=cdp.get('v4mgmtaddr'), username='?????', password='?????')
                Wire(node_n=tor, port_n=peer_port_id, node_s=n91, port_s=own_port_id, port_channel='uplink', vlans=[], mac=None)
                nodes.setdefault('tor', tor)
            else:
                ip = cdp.get('v4mgmtaddr')
                if n92 and n92.get_oob()[0] != ip:
                    raise RuntimeError('Failed to detect peer: different ips: {} and {}'.format(n92.get_oob()[0], ip))
                if not n92:
                    n92 = Nexus(node_id='n92', role=Nexus.ROLE, lab='fake-lab')
                    n92.set_oob_creds(ip=ip, username=n9_username, password=n9_password)
                Wire(node_n=n92, port_n=peer_port_id, node_s=n91, port_s=peer_port_id, port_channel='peer-link', vlans=[], mac=None)

        lldps = n91.n9_show_lldp_neighbor()
        cimc_username = 'admin'
        cimc_password = 'cisco123!'

        def normalize_mac(a):
            return ':'.join([a[0:2], a[2:4], a[5:7], a[7:9], a[10:12], a[12:14]])

        for lldp in lldps:
            own_port_id = lldp.get('l_port_id').replace('Eth', 'Ethernet')
            # own_port_info = ports[own_port_id]
            peer_mac = normalize_mac(lldp['port_id'])
            if peer_mac not in self._mac_host:
                continue
            # peer_mgmt_mac = lldp['chassis_id']
            cimc_ip = lldp.get('mgmt_addr')
            cimc_ip = self.get_ip('Something connected to {} with mac {}, CIMC address not known , please provide it'.format(own_port_id, peer_mac), None) if 'not advertised' in cimc_ip else cimc_ip

            cimc_username = prompt(text='Enter username for N9K at {} (default is {}): '.format(cimc_ip, cimc_username)) or cimc_username
            cimc_password = prompt(text='Enter password for N9K at {} (default is {}): '.format(cimc_ip, cimc_password)) or cimc_password
            cimc = CimcServer(node_id='???', role='???', lab='fake-lab')
            cimc.set_oob_creds(ip=cimc_ip, username=cimc_username, password=cimc_password)
            # loms = cimc.cimc_list_lom_ports()
            nodes[1] = cimc

    def execute(self, lab_name):
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

        cfg = self.read_config_from_file(yaml_path)

        lab = Laboratory(config_path=None)
        lab._lab_name = yaml_path.split('/')[-2]
        lab.set_lab_type('MERCURY-' + cfg['MECHANISM_DRIVERS'].upper())
        lab._id = 909

        nets = list()
        for net_info in cfg['NETWORKING']['networks']:
            cidr = net_info.get('subnet')
            if not cidr:
                continue
            segment = net_info['segments'][0]
            net_name = 'mx' if 'management' in segment else segment[0]

            if net_name == 'mx':
                mac_pattern = '99'
            elif net_name == 't':
                mac_pattern = 'cc'
            elif net_name == 's':
                mac_pattern = 'dd'
            elif net_name == 'a':
                mac_pattern = 'aa'
            elif net_name == 'e':
                mac_pattern = 'ff'
            else:
                raise ValueError('unxepected network segment found: {}'.format(segment))
            vlan_id = net_info['vlan_id']
            nets.append({'net-id': net_name, 'vlan': vlan_id, 'mac-pattern': mac_pattern, 'cidr': cidr})
        lab.add_networks(nets)

        cimc_username = cfg['CIMC-COMMON']['cimc_username']
        cimc_password = cfg['CIMC-COMMON']['cimc_password']
        ssh_username = cfg['COBBLER']['admin_username']
        ssh_password = 'cisco123'

        nodes = []

        for i, sw in enumerate(cfg['TORSWITCHINFO']['SWITCHDETAILS'], start=1):
            nodes.append({'node-id': 'n9' + str(i), 'role': 'n9', 'oob-ip': sw['ssh_ip'], 'oob-username': sw['username'], 'oob-password': sw['password'], 'ssh-username': 'None', 'ssh-password': 'None'})

        nodes.append({'node-id': 'mgm', 'role': 'director-n9', 'oob-ip': cfg['TESTING_MGMT_NODE_CIMC_IP'], 'oob-username': cfg['TESTING_MGMT_CIMC_USERNAME'], 'oob-password': cfg['TESTING_MGMT_CIMC_PASSWORD'],
                      'ssh-username': ssh_username, 'ssh-password': ssh_password})

        for role, node_ids in cfg['ROLES'].items():
            for node_id in node_ids:
                role_sqe = role + '-n9'
                try:
                    srv_mercury = cfg['SERVERS'][node_id]
                    oob_ip = srv_mercury['cimc_info']['cimc_ip']
                    oob_username = srv_mercury['cimc_info'].get('cimc_username', cimc_username)
                    oob_password = srv_mercury['cimc_info'].get('cimc_password', cimc_password)

                    mx_ip = srv_mercury['management_ip']
                    t_ip = srv_mercury['tenant_ip']
                    nodes.append({'node-id': node_id, 'role': role_sqe, 'oob-ip': oob_ip, 'oob-username': oob_username, 'oob-password': oob_password, 'ssh-username': ssh_username, 'ssh-password': ssh_password})
                except KeyError as ex:
                    raise KeyError('{}: no {}'.format(node_id, ex))
        lab.add_nodes(nodes)
        lab.save_lab_config()
