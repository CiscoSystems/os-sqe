from lab.lab_node import LabNode


class Nexus(LabNode):

    def __init__(self, node_id, role, lab, hostname):
        super(Nexus, self).__init__(node_id=node_id, role=role, lab=lab, hostname=hostname)
        self._actual_vpc = []
        self._actual_pc = {}
        self._actual_vlans = {}
        self._actual_ports = {}

    def __repr__(self):
        ip, username, password = self.get_oob()
        return u'{l} {id} sshpass -p {p} ssh {u}@{ip} use http://{ip} for NX-API'.format(l=self.lab(), id=self.get_id(), p=password, u=username, ip=ip)

    def get_pcs_to_fi(self):
        """Returns a list of pcs used on connection to peer N9K and both FIs"""
        return set([str(x.get_pc_id()) for x in self._downstream_wires if x.is_n9_fi()])

    def _allow_feature_nxapi(self):
        from fabric.api import settings, run

        oob_ip, oob_u, oob_p = self.get_oob()
        with settings(host_string='{user}@{ip}'.format(user=oob_u, ip=oob_ip), password=oob_p):
            if 'disabled'in run('sh feature | i nxapi', shell=False):
                run('conf t ; feature nxapi', shell=False)

    def _rest_api(self, commands, timeout=2):
        import requests
        import json
        from lab.logger import lab_logger
        lab_logger.info('{0} commands: {1}'.format(self, ", ".join(commands)))

        oob_ip, oob_u, oob_p = self.get_oob()
        body = [{"jsonrpc": "2.0", "method": "cli", "params": {"cmd": command, "version": 1}, "id": 1} for command in commands]
        try:
            data = json.dumps(body)
            result = requests.post('http://{0}/ins'.format(oob_ip), auth=(oob_u, oob_p), headers={'content-type': 'application/json-rpc'}, data=data, timeout=timeout)
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

    def n9_show_port_channels(self):
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
        for pc_id, port_ids in self.n9_show_port_channels().iteritems():
            if pc_id in skip_list:
                continue
            self.cmd(['conf t', 'no int port-channel {0}'.format(pc_id)], timeout=60)
            if port_ids:
                self.cmd(['conf t', 'int ethernet {0}'.format(','.join(port_ids)), 'description --'])

    def n9_configure_port(self, pc_id, port_id, vlans_string, desc, speed):
        actual_port_info = self._actual_ports['Ethernet' + port_id]
        actual_state, actual_desc = actual_port_info['state'], actual_port_info.get('name', '--')  # for port with no description this field either -- or not in dict

        if actual_state == 'xcvrAbsent':
            raise RuntimeError('N9K {}: Port {} seems to be not connected. Check your configuration'.format(self, port_id))

        actual_port_channel = filter(lambda x: port_id in x[1], self._actual_pc.items())
        actual_pc_id = int(actual_port_channel[0][0]) if actual_port_channel else 0

        if actual_pc_id:
            if actual_pc_id == pc_id:  # this port already part of required port-channel, so just change description once again
                self.cmd(['conf t', 'int ether ' + port_id, 'desc {0}'.format(desc)])
                return
            else:
                raise RuntimeError('N9K {}: Port {} belongs to different port-channel {}. Check your configuration'.format(self, port_id, actual_pc_id))
        # at hist point we know that port does not participate in port-channel

        if actual_state == 'down':
            self.cmd(['conf t', 'int ether ' + port_id, 'no shut'])

        if actual_desc != '--':  # if description is not default try to check which lab using it
            if not actual_desc.startswith(str(self.lab())):  # if it says the current lab, (almost) nothing to worry about
                raise RuntimeError('N9K {}: Port {} seems to belong to other lab (with description {}). Check your configuration'.format(self, port_id, actual_desc))
        # at this point we known that this port is not in port-channel and not possible belongs to other lab, so configure it
        self.cmd(['conf t', 'int ether ' + port_id, 'desc {0}'.format(desc), 'switchport', 'switchport mode trunk', 'switchport trunk allowed vlan {0}'.format(vlans_string), 'speed {0}'.format(speed)])

    def n9_create_port_channel(self, pc_id, desc, port_ids, speed, vlans_string, is_peer_link_pc=False):
        """
        :param is_peer_link_pc:
        :param desc: some text to describe port channel and it's ports
        :param vlans_string: string like '1, 12, 333-444'
        :param speed: int like 10000
        :param port_ids: port like '1/15'  it's a single value, one need to call this method few times with different port_id to add more ports to port-channel
        :param pc_id: id in range 1-4096
        :return:
        """
        for port_id in port_ids:
            self.n9_configure_port(pc_id=pc_id, port_id=port_id, vlans_string=vlans_string, desc=desc, speed=speed)

        actual_port_ids = self._actual_pc.get(str(pc_id), [])
        if actual_port_ids:  # port channel with this id already exists
            if port_ids != actual_port_ids:  # make sure that requested list of port-ids equals to actual list
                raise RuntimeError('{}: port-channel {} has different list of ports ({}) then requested ({})'.format(self, pc_id, actual_port_ids, port_ids))
            self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'switchport trunk allowed vlan add {0}'.format(vlans_string)])
        else:  # port channel is not yet created
            self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'descr {0}'.format(desc), 'switchport', 'switchport mode trunk', 'switchport trunk allowed vlan add {0}'.format(vlans_string),
                      'spanning-tree port type edge trunk', 'speed {0}'.format(speed), 'shut', 'no lacp suspend-individual', 'no shut'])
            for port_id in port_ids:  # add ports to the port-channel
                self.cmd(['conf t', 'int ethernet ' + port_id, 'channel-group {0} force mode active'.format(pc_id)])
            if is_peer_link_pc:
                self.n9_create_vpc_peer_link(pc_id)

    def n9_create_vpc(self, pc_id):
        if not self._actual_vpc:
            self.n9_get_status()
        if str(pc_id) not in self._actual_vpc:
            self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'vpc {0}'.format(pc_id)], timeout=60)

    def n9_get_status(self):
        self._actual_vpc = self.n9_show_vpc()
        self._actual_pc = self.n9_show_port_channels()
        self._actual_vlans = self.n9_show_vlans()
        self._actual_ports = self.n9_show_ports()

    def n9_show_ports(self):
        ans_st = self.cmd(['sh int st'])
        ans_br = self.cmd(['sh int br'])

        list_of_dicts = ans_br['result']['body'][u'TABLE_interface'][u'ROW_interface']
        result = {x['interface']: x for x in list_of_dicts}
        for dic in ans_st['result']['body'][u'TABLE_interface'][u'ROW_interface']:
            result[dic['interface']]['name'] = dic.get('name', '')
        return result

    def n9_show_vpc(self):
        ans = self.cmd(['sh vpc'])
        if ans['result']:
            vpc = ans['result']['body'][u'TABLE_vpc'][u'ROW_vpc']
            vpc = [vpc] if isinstance(vpc, dict) else vpc  # if there is only one vpc the API returns dict but not a list. Convert to list
            return map(lambda x: str(x['vpc-id']), vpc)
        else:
            return []

    def n9_create_vpc_peer_link(self, pc_id):
        self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'spanning-tree port type network', 'vpc peer-link'], timeout=180)

    def n9_show_vlans(self):
        vlans = self.cmd(['sh vlan'])
        if vlans['result']:
            vlans = vlans['result']['body'][u'TABLE_vlanbrief'][u'ROW_vlanbrief']
            vlans = [vlans] if isinstance(vlans, dict) else vlans
            result = {x['vlanshowbr-vlanid-utf']: {'name': x['vlanshowbr-vlanname'], 'ports': x['vlanshowplist-ifidx']} for x in vlans}
            return result
        else:
            return {}

    def n9_show_cdp_neighbor(self):
        cdp_neis = self.cmd(['sh cdp nei det'])
        return cdp_neis['result']['body']['TABLE_cdp_neighbor_detail_info']['ROW_cdp_neighbor_detail_info']

    def n9_show_users(self):
        res = self.cmd(['show users'])
        if res == 'timeout':
            return []
        if res['result']:
            return res['result']['body']['TABLE_sessions']['ROW_sessions']
        else:
            return []  # no current session

    def delete_vlans(self, slice_vlans=64):
        vlans = [x['vlanshowbr-vlanid-utf'] for x in self.n9_show_vlans() if x['vlanshowbr-vlanid-utf'] != '1']
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

    def n9_configure_vxlan(self, asr_port):
        import re

        number_in_node_id = map(int, re.findall(r'\d+', self.get_id()))[0]
        lo1_ip = '1.1.1.{0}'.format(number_in_node_id)
        lo2_ip = '2.2.2.{0}'.format(number_in_node_id)
        router_ospf = '111'
        router_area = '0.0.0.0'
        eth48_ip = '169.0.{0}.1'.format(number_in_node_id)
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

    def n9_configure_vpc_domain(self, peer_ip, domain_id=1):
        self.cmd(['conf t', 'feature vpc'])
        self.cmd(['conf t', 'vpc domain {0}'.format(domain_id), 'peer-keepalive destination {0}'.format(peer_ip)], timeout=60)

    def get_peer_link_id(self):
        return self._peer_link_wires[0].get_pc_id()

    def cleanup(self):
        self.delete_port_channels()
        self.delete_vlans()
        self.clean_interfaces()
        self.clean_vpc_domain()

    def n9_add_vlan_range(self, interfaces):
        vlan_range = self.lab().vlan_range().replace(':', '-')
        commands = ['conf t', 'vlan {0}'.format(vlan_range), 'no shut', 'exit', 'int e{0}'.format(',e'.join(interfaces)), 'switchport trunk allowed vlan add {0}'.format(vlan_range), 'end']
        self.cmd(commands)

    def n9_configure_vlans(self):
        if not self._actual_vlans:
            self.n9_get_status()
        vlans = []
        for net in self.lab().get_all_nets().values():
            vlan_id = str(net.get_vlan())
            if vlan_id == '1':
                continue
            vlans.append(vlan_id)
            vlan_name = '{}-{}{}{}'.format(self._lab, net.get_name(), '-VTS' if net.is_vts() else '', '-SSH' if net.is_ssh() else '')
            if vlan_id in self._actual_vlans:
                actual_vlan_name, actual_vlan_ports = self._actual_vlans[vlan_id]['name'], self._actual_vlans[vlan_id]['ports']
                if actual_vlan_name.lower() != vlan_name.lower():
                    raise RuntimeError('{}: vlan id {} already active with name {}. Don know what to do. please decide manually'.format(self, vlan_id, actual_vlan_name))
                self.log(message='VLAN id={} already active'.format(vlan_id))
            else:
                self.cmd(['conf t', 'vlan {}'.format(vlan_id), 'name ' + vlan_name, 'no shut'])
        return vlans

    def n9_configure_for_lab(self, topology):
        from lab.logger import lab_logger

        lab_logger.info('Configuring {0}'.format(self))

        self.n9_get_status()
        self.cmd(['conf t', 'feature lacp'])

        all_vlan_ids = self.n9_configure_vlans()

        self.n9_configure_peer_link(all_vlan_ids=all_vlan_ids)
        self.n9_configure_ports(wires=self._upstream_wires)
        self.n9_configure_ports(wires=self._downstream_wires)

        if topology == self.lab().TOPOLOGY_VXLAN:
            self.n9_configure_asr1k()

    def n9_configure_ports(self, wires):
        pc_id_vs_list_of_wires_dict = self.collect_port_channels(wires)
        for pc_id, wires in pc_id_vs_list_of_wires_dict.items():
            ports = reduce(lambda lst, w: lst + [w.get_own_port(self)], wires, [])
            if 'MGMT' in ports:  # don;t process MGMT ports
                continue
            description = str(wires[0].get_peer_node(self)) if not wires[0].is_n9_tor() else 'TOR uplink'
            vlans_string = ','.join(map(lambda x: str(x), wires[0].get_vlans()))  # the same list of vlans should on each wire
            if str(pc_id).startswith('FAKE-PC-ID'):  # this is actually a single port not participating in port-channel
                self.n9_configure_port(pc_id=pc_id, port_id=ports[0], vlans_string=vlans_string, desc=description, speed=10000)
            else:
                self.n9_create_port_channel(pc_id=pc_id, desc=description, port_ids=ports, vlans_string=vlans_string, speed=10000)
                if self._peer_link_wires:
                    self.n9_create_vpc(pc_id)

    @staticmethod
    def collect_port_channels(wires):
        pc_id_vs_list_of_wires_dict = {}
        no_pc_wires_count = 0
        for wire in wires:
            pc_id = wire.get_pc_id()
            if pc_id is None:
                no_pc_wires_count += 1
                pc_id = 'FAKE-PC-ID-' + str(no_pc_wires_count)
            pc_id_vs_list_of_wires_dict.setdefault(pc_id, [])
            pc_id_vs_list_of_wires_dict[pc_id].append(wire)
        return pc_id_vs_list_of_wires_dict

    def n9_configure_peer_link(self, all_vlan_ids):
        if not self._peer_link_wires:  # this N9K is not in per-link configuration
            return
        pc_id_vs_list_of_wires_dict = self.collect_port_channels(self._peer_link_wires)
        if len(pc_id_vs_list_of_wires_dict) != 1:
            raise ValueError('{}: Check lab config since peer-link port-channel needs to be formed from wires on the same port-channel-id')
        pc_id, wires = pc_id_vs_list_of_wires_dict.items()[0]
        peer_n9ks = map(lambda x: x.get_peer_node(self), wires)
        if len(set(peer_n9ks)) != 1:
            raise ValueError('{}: Check lab config since peer-link port-channel is form from ports wired to different devices: {}'.format(self, peer_n9ks))

        ports = map(lambda x: x.get_own_port(self), wires)

        vlans_string = ','.join(map(lambda x: str(x), all_vlan_ids))  # all vlans which go via peer-link: actually all lab vlans
        ip, _, _ = peer_n9ks[0].get_oob()
        self.n9_configure_vpc_domain(peer_ip=ip)
        self.n9_create_port_channel(pc_id=pc_id, desc='N9K peer-link', port_ids=ports, vlans_string=vlans_string, speed=10000, is_peer_link_pc=True)

    def n9_configure_asr1k(self):
        self.cmd(['conf t', 'int po{0}'.format(self.get_peer_link_id()), 'shut'])
        asr = filter(lambda x: x.is_n9_asr(), self._upstream_wires)
        self.n9_configure_vxlan(asr[0].get_own_port(self))

    def form_mac(self, pattern):
        pass
