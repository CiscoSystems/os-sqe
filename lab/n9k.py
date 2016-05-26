from lab.lab_node import LabNode


class Nexus(LabNode):
    def __init__(self, name, role, ip, username, password, lab, hostname):
        super(Nexus, self).__init__(name=name, role=role, ip=ip, username=username, password=password, lab=lab, hostname=hostname)
        self._vpc = []
        self._pc = {}
        self._vlans = {}

    def get_pcs_to_fi(self):
        """Returns a list of pcs used on connection to peer N9K and both FIs"""
        return set([str(x.get_pc_id()) for x in self._downstream_wires if x.is_n9_fi()])

    def _allow_feature_nxapi(self):
        from fabric.api import settings, run

        with settings(host_string='{user}@{ip}'.format(user=self._username, ip=self._ip), password=self._password):
            if 'disabled'in run('sh feature | i nxapi', shell=False):
                run('conf t ; feature nxapi', shell=False)

    def _rest_api(self, commands, timeout=2):
        import requests
        import json
        from lab.logger import lab_logger
        lab_logger.info('{0} commands: {1}'.format(self, ", ".join(commands)))

        body = [{"jsonrpc": "2.0", "method": "cli", "params": {"cmd": command, "version": 1}, "id": 1} for command in commands]
        try:
            data = json.dumps(body)
            result = requests.post('http://{0}/ins'.format(self._ip), auth=(self._username, self._password), headers={'content-type': 'application/json-rpc'}, data=data, timeout=timeout)
            return result.json()
        except requests.exceptions.ConnectionError:
            self._allow_feature_nxapi()
            return self._rest_api(commands=commands, timeout=timeout)

    def get_hostname(self):
        res = self.cmd(['sh switchname'])
        return res['result']['body']['hostname']

    def cmd(self, commands, timeout=15):
        if isinstance(commands, basestring):  # it might be provided as a string where commands are separated by ','
            commands = commands.strip('[]')
            commands = commands.split(',')

        results = self._rest_api(commands=commands, timeout=int(timeout))
        if len(commands) == 1:
            results = [results]
        for i, x in enumerate(results, start=0):
            if 'error' in x:
                raise NameError('{cmd} : {msg}'.format(msg=x['error']['data']['msg'].strip('%\n'), cmd=commands[i]))
        return dict(results[0])

    def change_port_state(self, port_no, port_state="no shut"):
        """
        Change port state of the port
        :param port_no: should be in full format like e1/3 or po1
        :param port_state: 'shut' or 'no shut'
        """
        self.cmd(['conf t', 'int {port}'.format(port=port_no), '{0}'.format(port_state)])

    def show_port_channel_summary(self):
        res = self.cmd(['show port-channel summary'])
        return [x['port-channel'] for x in res['result']['body']['TABLE_channel']['ROW_channel']]

    def show_interface_switchport(self, name):
        res = self.cmd(['show interface {0} switchport'.format(name)])
        vlans_str = res['result']['body']['TABLE_interface']['ROW_interface']['trunk_vlans']
        vlans = set()
        for vlan_range in vlans_str.split(','):  # from  1,2,5-7  to (1, 2, 5, 6, 7)
            se = vlan_range.split('-')
            if len(se) == 2:
                vlans = vlans | set(range(int(se[0]), int(se[1]) + 1))
            elif len(se) == 1:
                vlans.add(int(se[0]))
        return sorted(vlans)

    def show_port_channels(self):
        ans = self.cmd(['sh port-channel summary'])
        if ans['result']:
            pcs = ans['result']['body'][u'TABLE_channel'][u'ROW_channel']
            pcs = [pcs] if isinstance(pcs, dict) else pcs  # if there is only one port-channel the API returns dict but not a list. Convert to list
            port_channels = {}
            for pc_dict in pcs:
                pc_id = pc_dict['group']
                if 'TABLE_member' in pc_dict:
                    ports = pc_dict['TABLE_member']['ROW_member']  # if pc has only one port - it's a dict, otherwise - list
                    ports = [ports] if type(ports) == dict else ports
                    port_ids = map(lambda x: x['port'].replace('Ethernet', ''), ports)
                else:
                    port_ids = []
                port_channels[pc_id] = port_ids
            return port_channels
        else:
            return []

    def delete_port_channels(self, skip_list=None):
        skip_list = skip_list or []
        for pc_id, port_ids in self.show_port_channels().iteritems():
            if pc_id in skip_list:
                continue
            self.cmd(['conf t', 'no int port-channel {0}'.format(pc_id)], timeout=60)
            if port_ids:
                self.cmd(['conf t', 'int ethernet {0}'.format(','.join(port_ids)), 'description --'])

    def create_port_channel(self, pc_id, pc_name, ports, speed, vlans, is_peer_link_pc=False):
        """
        :param is_peer_link_pc:
        :param pc_name: some text to describe port channel and it's ports
        :param vlans: array of vlans like [1, 12, 333] or string like '1, 12, 333-444'
        :param speed: int like 10000
        :param ports: array of ports like ['1/15', '1/16']
        :param pc_id: id in range 1-4096
        :return:
        """
        # create port channel
        vlans_string = ','.join(map(lambda x: str(x), vlans)) if type(vlans) == list else vlans
        existing_port_ids = self._pc.get(str(pc_id), [])
        if existing_port_ids:  # port channel with this id already exists, so we assume it's shared with some other lab
            if existing_port_ids != ports:  # make sure that the list of ports on this port channel is the same as requested list of ports
                raise RuntimeError('{sw} has different list of ports ({e_p}) then requested ({r_p})'.format(sw=self, e_p=existing_port_ids, r_p=ports))
            self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'switchport trunk allowed vlan {0}'.format(vlans_string)])
        else:  # port channel is not yet created
            self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'description {0}'.format(pc_name),
                      'switchport', 'switchport mode trunk', 'switchport trunk allowed vlan add {0}'.format(vlans_string),
                      'spanning-tree port type edge trunk', 'speed {0}'.format(speed), 'shut', 'no lacp suspend-individual', 'no shut'])
            for port in ports:  # add ports to the port-channel
                self.cmd(['conf t', 'int ethernet ' + port, 'description {0}'.format(pc_name), 'switchport', 'switchport mode trunk', 'switchport trunk allowed vlan add {0}'.format(vlans_string),
                          'speed {0}'.format(speed), 'channel-group {0} mode active'.format(pc_id)])
            if is_peer_link_pc:
                self.create_vpc_peer_link(pc_id)

    def create_vpc(self, pc_id):
        if str(pc_id) not in self._vpc:
            self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'vpc {0}'.format(pc_id)], timeout=60)

    def get_status(self):
        self._vpc = self.show_vpc()
        self._pc = self.show_port_channels()
        self._vlans = self.show_vlans()

    def show_vpc(self):
        ans = self.cmd(['sh vpc'])
        if ans['result']:
            vpc = ans['result']['body'][u'TABLE_vpc'][u'ROW_vpc']
            vpc = [vpc] if isinstance(vpc, dict) else vpc  # if there is only one vpc the API returns dict but not a list. Convert to list
            return map(lambda x: str(x['vpc-id']), vpc)
        else:
            return []

    def create_vpc_peer_link(self, pc_id):
        self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'spanning-tree port type network', 'vpc peer-link'], timeout=180)

    def show_vlans(self):
        vlans = self.cmd(['sh vlan'])
        if vlans['result']:
            vlans = vlans['result']['body'][u'TABLE_vlanbrief'][u'ROW_vlanbrief']
            vlans = [vlans] if isinstance(vlans, dict) else vlans
            return vlans

    def show_cdp_neighbor(self):
        cdp_neis = self.cmd(['sh cdp nei det'])
        return cdp_neis['result']['body']['TABLE_cdp_neighbor_detail_info']['ROW_cdp_neighbor_detail_info']

    def show_users(self):
        res = self.cmd(['show users'])
        if res == 'timeout':
            return []
        if res['result']:
            return res['result']['body']['TABLE_sessions']['ROW_sessions']
        else:
            return []  # no current session

    def delete_vlans(self, slice_vlans=64):
        vlans = [x['vlanshowbr-vlanid-utf'] for x in self.show_vlans() if x['vlanshowbr-vlanid-utf'] != '1']
        vlan_delete_str = ['conf t'] + ['no vlan ' + ','.join(vlans[i:i+slice_vlans]) for i in range(0, len(vlans), slice_vlans)]
        self.cmd(vlan_delete_str)

    def clean_interfaces(self):
        interfaces = set([x.get_own_port(self) for x in self._peer_link_wires + self._downstream_wires])
        clean_cmd = ['conf t']
        [clean_cmd.extend(['int e{0}'.format(x), 'no description', 'switchport trunk allowed vlan none', 'exit']) for x in interfaces]
        self.cmd(clean_cmd, timeout=60)

    def clean_vpc_domain(self):
        old_vpc_domain = self.cmd(['sh vpc'])['result']['body']['vpc-domain-id']
        if old_vpc_domain != 'not configured':
            self.cmd(['conf t', 'no vpc domain {0}'.format(old_vpc_domain)], timeout=60)

    def configure_vxlan(self, asr_port):
        lo1_ip = '1.1.1.{0}'.format(self.node_index())
        lo2_ip = '2.2.2.{0}'.format(self.node_index())
        router_ospf = '111'
        router_area = '0.0.0.0'
        eth48_ip = '169.0.{0}.1'.format(self.node_index())
        self.cmd(['conf t', 'feature ospf'])
        self.cmd(['conf t', 'feature pim'])
        self.cmd(['conf t', 'interface loopback 1'])
        self.cmd(['conf t', 'interface loopback 2'])
        self.cmd(['conf t', 'interface loopback 1', 'ip address {0}/32'.format(lo1_ip)])
        self.cmd(['conf t', 'interface loopback 1', 'ip router ospf {0} area {1}'.format(router_ospf, router_area)])
        self.cmd(['conf t', 'interface loopback 2', 'ip address {0}/32'.format(lo2_ip)])
        self.cmd(['conf t', 'interface loopback 2', 'ip router ospf {0} area {1}'.format(router_ospf, router_area)])
        self.cmd(['conf t', 'interface ethernet {0}'.format(asr_port), 'no switchport'])
        self.cmd(['conf t', 'interface ethernet {0}'.format(asr_port), 'ip address {0}/30'.format(eth48_ip)])
        self.cmd(['conf t', 'interface ethernet {0}'.format(asr_port), 'ip router ospf {0} area {1}'.format(router_ospf, router_area)])

    def configure_vpc_domain(self, peer_ip, domain_id=1):
        self.cmd(['conf t', 'feature vpc'])
        self.cmd(['conf t', 'vpc domain {0}'.format(domain_id), 'peer-keepalive destination {0}'.format(peer_ip)], timeout=60)

    def get_peer_link_id(self):
        return self._peer_link_wires[0].get_pc_id()

    def cleanup(self):
        self.delete_port_channels()
        self.delete_vlans()
        self.clean_interfaces()
        self.clean_vpc_domain()

    def add_vlan_range(self, interfaces):
        vlan_range = self.lab().vlan_range().replace(':', '-')
        commands = ['conf t', 'vlan {0}'.format(vlan_range), 'no shut', 'exit', 'int e{0}'.format(',e'.join(interfaces)), 'switchport trunk allowed vlan add {0}'.format(vlan_range), 'end']
        self.cmd(commands)

    def configure_for_lab(self, topology):
        from lab.logger import lab_logger

        lab_logger.info('Configuring {0}'.format(self))

        self.get_status()
        self.cmd(['conf t', 'feature lacp'])

        all_vlans = ', '.join(map(lambda x: str(x), self.lab().get_all_vlans()))
        self.cmd(['conf t', 'vlan {0}'.format(all_vlans), 'name {0}'.format(self._lab), 'no shut'])

        def get_pc_info(wires):
            peers = map(lambda x: x.get_peer_node(self), self._peer_link_wires)
            if len(set(peers)) > 1:
                raise ValueError('{0} has a peer-link config which has wrong peer nodes info - not all of them are the same: {1}'.format(self, wires))
            pc_ids = map(lambda x: x.get_pc_id(), self._peer_link_wires)
            if len(set(peers)) > 1:
                raise ValueError('{0} has a peer-link config which has wrong pc_id info - not all of them are the same: {1}'.format(self, wires))
            return pc_ids[0], peers[0], map(lambda x: x.get_own_port(self), wires)

        if self._peer_link_wires:
            pc_id, peer, ports = get_pc_info(self._peer_link_wires)
            vlans = self.lab().get_vlans_to_tor()
            ip, _, _, _ = peer.get_ssh()
            self.configure_vpc_domain(peer_ip=ip)
            self.create_port_channel(pc_id=pc_id, pc_name='peer', ports=ports, vlans=vlans, speed=10000, is_peer_link_pc=True)

        for w in self._downstream_wires:
            ucs = w.get_peer_node(self)
            vlans = ucs.get_vlans()
            ports = [w.get_own_port(self)]
            pc_id = w.get_pc_id()
            self.create_port_channel(pc_id=pc_id, pc_name=str(ucs), ports=ports, vlans=vlans, speed=10000)
            if self._peer_link_wires:
                self.create_vpc(pc_id)

        for w in self._upstream_wires:
            ports = [w.get_own_port(self)]
            pc_id = w.get_pc_id()
            vlans = self.lab().get_vlans_to_tor()
            self.create_port_channel(pc_id=pc_id, pc_name='tor', ports=ports, vlans=vlans, speed=10000)
            if self._peer_link_wires:
                self.create_vpc(pc_id)

        if topology == self.lab().TOPOLOGY_VXLAN:
            self.cmd(['conf t', 'int po{0}'.format(self.get_peer_link_id()), 'shut'])
            asr = filter(lambda x: x.is_n9_asr(), self._upstream_wires)
            self.configure_vxlan(asr[0].get_own_port(self))
