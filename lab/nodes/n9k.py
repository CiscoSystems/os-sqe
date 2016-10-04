from lab.nodes import LabNode


class Nexus(LabNode):
    ROLE = 'n9'

    def __init__(self, node_id, role, lab):
        super(Nexus, self).__init__(node_id=node_id, role=role, lab=lab)
        self.__requested_topology = None

    @property
    def _requested_topology(self):
        if self.__requested_topology is None:
            self.__requested_topology = self.prepare_topology()
        return self.__requested_topology

    def __repr__(self):
        ip, username, password = self.get_oob()
        return u'{l} {id} NX-API: http://{ip} {u}/{p}'.format(l=self.lab(), id=self.get_id(), p=password, u=username, ip=ip)

    def get_pcs_to_fi(self):
        """Returns a list of pcs used on connection to peer N9K and both FIs"""
        return set([str(x.get_pc_id()) for x in self._downstream_wires if x.is_n9_fi()])

    def _allow_feature_nxapi(self):
        from fabric.api import settings, run

        oob_ip, oob_u, oob_p = self.get_oob()
        with settings(host_string='{user}@{ip}'.format(user=oob_u, ip=oob_ip), password=oob_p):
            if 'disabled'in run('sh feature | i nxapi', shell=False):
                run('conf t ; feature nxapi', shell=False)

    def _rest_api(self, commands, timeout=2, method='cli'):
        import requests
        import json
        from lab.logger import lab_logger
        lab_logger.info('{0} commands: {1}'.format(self, ", ".join(commands)))

        oob_ip, oob_u, oob_p = self.get_oob()
        body = [{"jsonrpc": "2.0", "method": method, "params": {"cmd": command, "version": 1}, "id": 1} for command in commands]
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

    def cmd(self, commands, timeout=15, method='cli'):
        if type(commands) is not list:  # it might be provided as a string where commands are separated by ','
            commands = commands.strip('[]')
            commands = commands.split(',')

        results = self._rest_api(commands=commands, timeout=int(timeout), method=method)
        if len(commands) == 1:
            results = [results]
        for i, x in enumerate(results, start=0):
            if 'error' in x:
                raise NameError('{cmd} : {msg}'.format(msg=x['error']['data']['msg'].strip('%\n'), cmd=commands[i]))
        return dict(results[0])

    def n9_change_port_state(self, port_no, port_state="no shut"):
        """
        Change port state of the port
        :param port_no: should be in full format like e1/3 or po1
        :param port_state: 'shut' or 'no shut'
        """
        self.cmd(['conf t', 'int {}'.format(port_no), port_state])

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
                pc_id = pc_dict.get('group')
                if 'TABLE_member' in pc_dict:
                    ports = pc_dict.get('TABLE_member').get('ROW_member')  # if pc has only one port - it's a dict, otherwise - list
                    ports = [ports] if type(ports) == dict else ports
                    port_ids = map(lambda x: x['port'].replace('Ethernet', ''), ports)
                else:
                    port_ids = []
                port_channels[pc_id] = port_ids
            return port_channels
        else:
            return {}

    def n9_configure_port(self, pc_id, port_id, vlans_string, desc, mode):
        actual_port_info = self.n9_show_ports()['Ethernet' + port_id]
        actual_state, actual_desc = actual_port_info['state_rsn_desc'], actual_port_info.get('name', '--')  # for port with no description this field either -- or not in dict

        if actual_state in [u'XCVR not inserted']:
            raise RuntimeError('N9K {}: Port {} seems to be not connected. Check your configuration'.format(self, port_id))

        actual_port_channel = filter(lambda x: port_id in x[1], self.n9_show_port_channels().items())
        actual_pc_id = int(actual_port_channel[0][0]) if actual_port_channel else 0

        if actual_pc_id:
            if actual_pc_id == pc_id:  # this port already part of required port-channel, so just change description once again
                self.cmd(['conf t', 'int ether ' + port_id, 'desc {0}'.format(desc)])
                return
            else:
                raise RuntimeError('N9K {}: Port {} belongs to different port-channel {}. Check your configuration'.format(self, port_id, actual_pc_id))
        # at this point we know that port does not participate in port-channel

        if actual_state == 'down':
            self.cmd(['conf t', 'int ether ' + port_id, 'no shut'])

        if actual_desc not in ['--', '', 'PXE link', 'TOR uplink', 'peer link']:  # if description is not default try to check which lab using it
            if not actual_desc.startswith(str(self.lab())):  # if it says the current lab, (almost) nothing to worry about
                raise RuntimeError('N9K {}: Port {} seems to belong to other lab (with description {}). Check your configuration'.format(self, port_id, actual_desc))
        # at this point we known that this port is not in port-channel and not possibly belongs to other lab, so configure it
        self.cmd(['conf t', 'int ether ' + port_id, 'desc {0}'.format(desc), 'switchport', 'switchport mode ' + mode, 'switchport {} vlan {}'.format('trunk allowed' if mode == 'trunk' else 'access', vlans_string)])

    def n9_create_port_channel(self, pc_id, desc, port_ids, vlans_string, mode, is_peer_link_pc=False):
        for port_id in port_ids:
            self.n9_configure_port(pc_id=pc_id, port_id=port_id, vlans_string=vlans_string, desc=desc, mode=mode)

        actual_port_ids = self.n9_show_port_channels().get(str(pc_id), [])
        if actual_port_ids:  # port channel with this id already exists
            if port_ids != actual_port_ids:  # make sure that requested list of port-ids equals to actual list
                raise RuntimeError('{}: port-channel {} has different list of ports ({}) then requested ({})'.format(self, pc_id, actual_port_ids, port_ids))
            self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'switchport {} vlan {}'.format('trunk allowed' if mode == 'trunk' else 'access', vlans_string)])
        else:  # port channel is not yet created
            self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'descr {0}'.format(desc), 'switchport', 'switchport mode ' + mode, 'switchport {} vlan {}'.format('trunk allowed' if mode == 'trunk' else 'access', vlans_string)])

            if is_peer_link_pc:
                self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'vpc peer-link'], timeout=180)
            else:
                self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'spanning-tree port type edge {}'.format('trunk' if mode == 'trunk' else ''), 'shut', 'no lacp suspend-individual', 'no shut'], timeout=180)

            for port_id in port_ids:  # add ports to the port-channel
                self.cmd(['conf t', 'int ethernet ' + port_id, 'channel-group {0} force mode active'.format(pc_id)])

    def n9_create_vpc(self, pc_id):
        if str(pc_id) not in self.n9_show_vpc():
            self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'vpc {0}'.format(pc_id)], timeout=60)

    def n9_delete_all_vlans(self):
        vlan_ids = [vlan_id for vlan_id in self.n9_show_vlans().keys() if vlan_id != '1']
        if vlan_ids:
            vlan_delete_str = ['conf t'] + ['no vlan ' + ','.join(vlan_ids[i:i+64]) for i in range(0, len(vlan_ids), 64)]  # need to slice since no more then 64 ids allowed per operation
            self.cmd(vlan_delete_str)

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

    def get_peer_linked_n9k(self):
        return self._peer_link_wires[0].get_peer_node(self)

    def n9_add_vlan_range(self, interfaces):
        vlan_range = self.lab().get_vlan_range().replace(':', '-')
        commands = ['conf t', 'vlan {0}'.format(vlan_range), 'no shut', 'exit', 'int e{0}'.format(',e'.join(interfaces)), 'switchport trunk allowed vlan add {0}'.format(vlan_range), 'end']
        self.cmd(commands)

    def n9_configure_vlans(self):
        vlans = self._requested_topology['vlans']
        actual_vlans = self.n9_show_vlans()
        for vlan_id, vlan_name in vlans.items():
            vlan_name = str(vlan_name)
            if vlan_id == '1':
                continue
            if str(vlan_id) in actual_vlans:
                actual_vlan_name = actual_vlans[str(vlan_id)]['name']
                if actual_vlan_name.lower() != vlan_name.lower():
                    raise RuntimeError('{}: vlan id {} already active with name "{}" while trying to assign name "{}". Handle it manually!'.format(self, vlan_id, actual_vlan_name, vlan_name))
                self.log(message='VLAN id={} already active'.format(vlan_id))
            else:
                self.cmd(['conf t', 'vlan {}'.format(vlan_id), 'name ' + vlan_name, 'no shut'])
        return vlans

    def n9_configure_for_lab(self):
        from lab.logger import lab_logger

        lab_logger.info('Configuring {0}'.format(self))
        self.cmd(['conf t', 'feature lacp', 'feature vpc'])

        self.n9_configure_vlans()
        self.n9_configure_peer_link()
        self.n9_configure_ports()
        self.n9_configure_vpc()

    def n9_configure_peer_link(self):
        peer_link = self._requested_topology['peer-link']
        ip = peer_link['ip']
        if ip:
            pc_id = peer_link['pc-id']
            desc = peer_link['description']
            port_ids = peer_link['ports']
            vlans_string = peer_link['vlans']
            self.n9_configure_vpc_domain(peer_ip=ip)
            self.n9_create_port_channel(pc_id=pc_id, desc=desc, port_ids=port_ids, vlans_string=vlans_string, mode='trunk', is_peer_link_pc=True)

    def n9_configure_vpc(self):
        vpc = self._requested_topology['vpc']
        for pc_id, info in vpc.items():
            self.n9_create_port_channel(pc_id=pc_id, desc=info['description'], port_ids=info['ports'], mode=info['mode'], vlans_string=info['vlans'])
            if self._peer_link_wires:
                self.n9_create_vpc(pc_id)

    def n9_configure_ports(self):
        ports = self._requested_topology['ports']
        for port_id, info in ports.items():
            self.n9_configure_port(pc_id=None, port_id=port_id, vlans_string=info['vlans'], desc=info['description'], mode=info['mode'])

    def prepare_topology(self):
        import functools

        requested_vlans = {}

        vlan_vs_net = {net.get_vlan(): net for net in self.lab().get_all_nets().values()}
        vlans_via_tor = []
        vlans_on_downstream = set(functools.reduce(lambda lst, w: lst + w.get_vlans(), self._downstream_wires, []))
        for vlan_id in vlans_on_downstream:
            net = vlan_vs_net[vlan_id]
            if net.is_via_tor():
                vlans_via_tor.append(vlan_id)
            vlan_name = '{lab_name}-{net_name}{ssh}'.format(lab_name=self._lab, net_name=net.get_name(), ssh='-SSH' if net.is_ssh() else '')
            requested_vlans[str(vlan_id)] = vlan_name

        requested_ports = {}
        requested_vpc = {}
        requested_peer_link = {'description': 'peer link', 'ip': None, 'vlans': ','.join(requested_vlans.keys()), 'ports': []}
        for wire in self.get_all_wires():
            own_port_id = wire.get_own_port(self)
            if own_port_id == 'MGMT':
                continue
            pc_id = wire.get_pc_id()
            if wire.is_n9_n9():
                requested_peer_link['pc-id'] = pc_id
                requested_peer_link['ports'].append(own_port_id)
                requested_peer_link['ip'] = wire.get_peer_node(self).get_oob()[0]
                continue
            elif wire.is_n9_tor():
                description = 'TOR uplink'
                vlans_on_wire = vlans_via_tor
                mode = 'trunk'
            elif wire.is_n9_pxe():
                description = 'PXE link'
                vlans_on_wire = ['1']
                mode = 'access'
            elif wire.is_n9_fi():
                description = '{} FI down link'.format(self.lab())
                mode = 'trunk'
                vlans_on_wire = wire.get_vlans()
            elif wire.is_n9_ucs():
                description = str(wire.get_peer_node(self))
                vlans_on_wire = wire.get_vlans()
                peer_port_id = wire.get_peer_port(self)
                if peer_port_id not in ['MLOM/0', 'MLOM/1', 'LOM-1', 'LOM-2']:
                    raise ValueError('{}: has strange port {}'.format(wire.get_peer_node(self), peer_port_id))
                mode = 'trunk' if 'MLOM' in peer_port_id else 'access'
            else:
                raise ValueError('{}:  strange wire which should not go to N9K: {}'.format(self, wire))
            vlans_string = ','.join(vlans_on_wire)
            if pc_id is None:  # it's a single port configuration
                requested_ports[own_port_id] = {'description': description, 'vlans': vlans_string, 'mode': mode}
            else:  # it's (v)PC
                requested_vpc.setdefault(pc_id, {'description': description, 'vlans': vlans_string, 'ports': [], 'mode': mode})
                requested_vpc[pc_id]['ports'].append(own_port_id)
        return {'vpc': requested_vpc, 'vlans': requested_vlans, 'ports': requested_ports, 'peer-link': requested_peer_link}

    def n9_configure_asr1k(self):
        self.cmd(['conf t', 'int po{0}'.format(self.get_peer_link_id()), 'shut'])
        asr = filter(lambda x: x.is_n9_asr(), self._upstream_wires)
        self.n9_configure_vxlan(asr[0].get_own_port(self))

    def n9_cleanup(self):
        self.n9_delete_vlan_interfaces()
        self.n9_delete_port_channels()
        self.n9_delete_all_vlans()
        self.n9_default_interfaces()
        self.n9_delete_vpc_domain()

    def n9_default_interfaces(self):
        last_port_id = max(map(lambda name: 0 if 'Ethernet' not in name else int(name.split('/')[-1]), self.n9_show_ports().keys()))
        self.cmd(['conf t', 'default int e 1/1-{}'.format(last_port_id)], timeout=60)

    def n9_delete_port_channels(self, skip_list=None):
        skip_list = skip_list or []
        for pc_id in self.n9_show_port_channels().keys():
            if pc_id in skip_list:
                continue
            self.cmd(['conf t', 'no int port-channel {0}'.format(pc_id)], timeout=60)

    def n9_delete_vpc_domain(self):
        vpc_domain_id = self.n9_show_vpc()['domain-id']
        if vpc_domain_id != 'not configured':
            self.cmd(['conf t', 'no vpc domain {}'.format(vpc_domain_id)], timeout=60)

    def n9_delete_vlan_interfaces(self):
        vlan_ifs = [if_id for if_id in self.n9_show_ports().keys() if 'Vlan' in if_id]
        for vlan_if in vlan_ifs:
            if_id = int(vlan_if.replace('Vlan', ''))
            if if_id != 1:
                self.cmd(['conf t', 'no int vlan {}'.format(if_id)])

    def n9_show_ports(self):
        ans_st = self.cmd(['sh int st'])
        ans_br = self.cmd(['sh int br'])

        list_of_dicts = ans_br['result']['body'][u'TABLE_interface'][u'ROW_interface']
        result = {x['interface']: x for x in list_of_dicts}
        for dic in ans_st['result']['body'][u'TABLE_interface'][u'ROW_interface']:
            result[dic['interface']]['name'] = dic.get('name', '')
        return result

    def n9_show_running_config(self):
        return self.cmd(commands=['sh run'], method='cli_ascii')['result']['msg']

    def n9_show_vpc(self):
        ans = self.cmd(['sh vpc'])
        vpc_domain_id = ans['result']['body']['vpc-domain-id']
        if 'TABLE_vpc' in ans['result']['body']:
            vpc = ans['result']['body'][u'TABLE_vpc'][u'ROW_vpc']
            vpc = [vpc] if isinstance(vpc, dict) else vpc  # if there is only one vpc the API returns dict but not a list. Convert to list
            vpc_ids = map(lambda x: str(x['vpc-id']), vpc)
        else:
            vpc_ids = []
        return {'domain-id': vpc_domain_id, 'vpc-ids': vpc_ids}

    def n9_show_vlans(self):
        vlans = self.cmd(['sh vlan'])
        if vlans['result']:
            vlans = vlans['result']['body'][u'TABLE_vlanbrief'][u'ROW_vlanbrief']
            vlans = [vlans] if isinstance(vlans, dict) else vlans
            result = {x.get('vlanshowbr-vlanid-utf'): {'name': x.get('vlanshowbr-vlanname'), 'ports': x.get('vlanshowplist-ifidx')} for x in vlans}
            return result
        else:
            return {}

    def n9_show_cdp_neighbor(self):
        cdp_neis = self.cmd(['sh cdp nei det'])
        return cdp_neis['result']['body']['TABLE_cdp_neighbor_detail_info']['ROW_cdp_neighbor_detail_info']

    def n9_show_lldp_neighbor(self):
        self.cmd(['conf t', 'feature lldp'])
        lldp_neis = self.cmd(['sh lldp nei det'])
        return lldp_neis['result']['body']['TABLE_nbor_detail']['ROW_nbor_detail']

    def n9_show_users(self):
        res = self.cmd(['show users'])
        if res == 'timeout':
            return []
        if res['result']:
            return res['result']['body']['TABLE_sessions']['ROW_sessions']
        else:
            return []  # no current session

    def r_border_leaf(self):
        vlans = self._requested_topology['vlans']
        tenant_vlan_ids = [vlan_id for vlan_id, name_and_others in vlans.items() if name_and_others['name'] == '{}-t'.format(self.lab())]
        if not tenant_vlan_ids:
            return  # this switch has no tenant vlan so do not configure border leaf on it

        tenant_vlan_id = tenant_vlan_ids[0]
        this_switch_bgp_nei_ip = '34.34.34.{}'.format(self._n)
        loopback_ip = '90.90.90.90'
        xrvr_bgp_ips = ['34.34.34.101', '34.34.34.102']
        self.cmd(['conf t', 'interface Vlan{}'.format(tenant_vlan_id), 'no shut', 'ip address {}/24'.format(this_switch_bgp_nei_ip), 'no ipv6 redirects', 'ip router ospf 100 area 0.0.0.0',
                  'hsrp 34 ', 'ip 34.34.34.100'], timeout=60)
        self.cmd(['conf t', 'interface loopback0', 'ip address {}/32'.format(loopback_ip), 'ip address 92.92.92.92/32 secondary', 'ip router ospf 100 area 0.0.0.0'], timeout=60)
        self.cmd(['conf t', 'router ospf 100', 'router-id {}'.format(this_switch_bgp_nei_ip), 'area 0.0.0.0 default-cost 10'], timeout=60)
        self.cmd(['conf t', 'router bgp 23', 'router-id {}'.format(this_switch_bgp_nei_ip), 'address-family ipv4 unicast', 'address-family l2vpn evpn', 'retain route-target all',
                  'neighbor {}'.format(xrvr_bgp_ips[0]), 'remote-as 23', 'update-source Vlan{}'.format(tenant_vlan_id), 'address-family l2vpn evpn', 'send-community both',
                  'neighbor {}'.format(xrvr_bgp_ips[1]), 'remote-as 23', 'update-source Vlan{}'.format(tenant_vlan_id), 'address-family l2vpn evpn', 'send-community both'], timeout=60)

    def r_collect_config(self):
        return self._format_single_cmd_output(cmd='show running config', ans=self.n9_show_running_config())
