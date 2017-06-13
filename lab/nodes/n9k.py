from lab.nodes import LabNode


class N9PortChannel(object):
    def __init__(self, n9_dic):
        self._dic = n9_dic
        self._ports = []

    def get_ports(self):
        return self._ports

    def get_pc_id(self):
        return self._dic['port-channel']

    def add_port(self, port):
        self._ports.append(port)

    def get_mode(self):
        return self._dic['portmode']

    def get_name(self):
        return self._dic.get('name', 'NoName')

    @staticmethod
    def process_n9_answer(a):  # process results of sh port-channel status
        pcs = [a] if type(a) is dict else a  # if there is only one port-channel the API returns dict but not a list. Convert to list
        return {x['port-channel']: N9PortChannel(n9_dic=x) for x in pcs}

    def update(self, dic):  # add info from sh int st and sh int br
        self._dic.update(dic)


class N9Port(object):
    def __init__(self, n9, pc_dic, n9_dic):
        self._n9 = n9
        self._dic = n9_dic
        self._pc = None

        if 'portchan' in n9_dic:
            self._pc = pc_dic['port-channel' + str(n9_dic['portchan'])]
            self._pc.add_port(self)

    def get_port_id(self):
        return self._dic['interface']

    def get_pc_id(self):
        return self._pc.get_pc_id() if self._pc else None

    def get_mode(self):
        return self._dic['portmode']

    def get_speed(self):
        return self._dic['speed']

    def get_state(self):
        state = self._dic['state']
        return state if state == 'up' else self._dic['state_rsn_desc']

    def get_vlans(self):
        return self._dic['vlan'] if self.get_mode() == 'access' else self._dic['vlan']  # TODO in trunk this field is always trunk

    def get_name(self):
        return self._dic.get('name', '--')  # for port with no description this field either -- or not in dict

    def is_not_connected(self):
        return self._dic['state_rsn_desc'] == u'XCVR not inserted'

    def is_down(self):
        return self._dic['state_rsn_desc'] == u'down'

    def handle(self, pc_id, port_name, port_mode, vlans):

        cmd_up = ['conf t', 'int ether ' + self.get_port_id(), 'no shut']
        cmd_make = ['conf t', 'int ' + self.get_port_id(), 'desc ' + port_name, 'switchport', 'switchport mode ' + port_mode, 'switchport {} vlan {}'.format('trunk allowed' if port_mode == 'trunk' else 'access', vlans)]
        cmd_name = ['conf t', 'int ' + self.get_port_id(), 'desc ' + port_name]
        if self.is_not_connected():
            raise RuntimeError('N9K {}: Port {} seems to be not connected. Check your configuration'.format(self, self.get_port_id()))
        a_pc_id = self.get_pc_id()
        if a_pc_id is None:
            self._n9.fix_problem(cmd=cmd_make, msg='port {} is not a part of any port channels'.format(self.get_port_id()))
        elif a_pc_id != pc_id:
            raise RuntimeError('N9K {}: Port {} belongs to different port-channel {}. Check your configuration'.format(self, self.get_port_id(), a_pc_id))

        if self.is_down():
            self._n9.fix_problem(cmd=cmd_up, msg='{} is down'.format(self.get_port_id()))

        a_name = self.get_name()
        if a_name != port_name:
            self._n9.fix_problem(cmd=cmd_name, msg='{} has actual description "{}" while requested is "{}"'.format(self.get_port_id(), a_name, port_name))


class N9VlanPort(object):
    def __init__(self, n9, n9_dict):
        self._n9 = n9
        self._dict = n9_dict


class N9neighbour(object):
    def __init__(self, n9_dic):
        self._dic = n9_dic

    def get_macs(self):
        return [self._dic.get('chassis_id', 'No_chassis_id'), self._dic['port_id']]

    def get_n9_port_id(self):
        return self._dic['l_port_id'].replace('Eth', 'Ethernet')

    @staticmethod
    def process_n9_answer(a):
        lst = a['TABLE_nbor_detail']['ROW_nbor_detail'] if type(a) is not list else a  # cdp retunrs list, lldp returns dict
        return [N9neighbour(n9_dic=x) for x in lst]

    @staticmethod
    def mac_n9_to_normal(m):
        return ':'.join([m[0:2], m[2:4], m[5:7], m[7:9], m[10:12], m[12:14]]).upper()  # 54a2.74cc.7f42 -> 54:A2:74:CC:7F:42

    @staticmethod
    def mac_normal_to_n9(m):
        return '.'.join([m[0:2] + m[3:5], m[6:8] + m[9:11], m[12:14] + m[15:]]).lower()  # 54:A2:74:CC:7F:42 -> 54a2.74cc.7f42

    @staticmethod
    def find_mac(mac, nei_lst):
        if ':' in mac:
            mac = N9neighbour.mac_normal_to_n9(m=mac)
        found = [x for x in nei_lst if mac in x.get_macs()]
        assert len(found) <= 1, 'More then 1 neighbour with the same MAC'
        return found[0] if found else None


class N9Vlan(object):
    def __init__(self, n9_dict):
        self._dict = n9_dict

    def get_name(self):
        return self._dict['vlanshowbr-vlanname']

    def get_id(self):
        return self._dict['vlanshowbr-vlanid']

    @staticmethod
    def get_cmd(vlan_id, vlan_name):
        return ['conf t', 'vlan ' + str(vlan_id), 'name ' + vlan_name, 'no shut']

    @staticmethod
    def process_n9_answer(a):
        return {x['vlanshowbr-vlanid']: N9Vlan(n9_dict=x) for x in a['TABLE_vlanbrief']['ROW_vlanbrief']}


class N9VpcDomain(object):
    def __init__(self, n9_dict):
        self._dict = n9_dict

    def get_id(self):
        return self._dict['vpc-domain-id']

    def is_configured(self):
        return self.get_id() != 'not configured'

    @staticmethod
    def process_n9_answer(a):
        peer_tbl = a.get('TABLE_peerlink', {'ROW_peerlink': []})['ROW_peerlink']
        vpc_tbl = a.get('TABLE_vpc', {'ROW_vpc': []})['ROW_vpc']
        vpc_lst = [vpc_tbl] if type(vpc_tbl) is dict else vpc_tbl  # if there is only one vpc the API returns dict but not a list. Convert to list
        vpc_dic = {x['vpc-ifindex']: x for x in vpc_lst}
        assert len(vpc_dic) == int(a['num-of-vpcs'])  # this is a number of vpc excluding peer-link vpc
        if peer_tbl:
            vpc_dic[peer_tbl['peerlink-ifindex']] = peer_tbl
        return N9VpcDomain(n9_dict=a), vpc_dic


class N9Status(object):

    def __init__(self, n9):
        self._n9 = n9
        a = n9.n9_cmd(['sh port-channel summary', 'sh int st', 'sh int br', 'sh vlan', 'sh cdp nei det', 'sh lldp nei det'] + (['sh vpc'] if n9.get_node_id() != 'n9n' else []), timeout=30)

        self._pc_dic = N9PortChannel.process_n9_answer(a=a['sh port-channel summary'])
        self._vpc_domain, vpc_dic = N9VpcDomain.process_n9_answer(a=a['sh vpc']) if 'sh vpc' in a else None, {}
        map(lambda vpc_id, vpc: self._pc_dic[vpc_id].update(vpc), vpc_dic.items())

        self._port_dic = {}
        self._vlan_port_dic = {}
        for st, br in zip(a['sh int st'], a['sh int br']):
            st.update(br)  # combine both since br contains pc info
            p_id = st['interface']
            if p_id.startswith('port-channel'):
                self._pc_dic[p_id].update(st)
            elif p_id.startswith('Vlan'):
                self._vlan_port_dic[p_id] = N9VlanPort(n9=n9, n9_dict=st)
            elif p_id.startswith('Ethernet'):
                self._port_dic[p_id] = N9Port(n9=self, n9_dic=st, pc_dic=self._pc_dic)
            else:
                continue
        self._neigh_lst = N9neighbour.process_n9_answer(a=a['sh lldp nei det'])
        self._neigh_lst.extend(N9neighbour.process_n9_answer(a=a['sh cdp nei det']))
        self._vlans = N9Vlan.process_n9_answer(a=a['sh vlan'])

    def get_n9_node_id(self):
        return self._n9.get_node_id()

    def get_n9_pc_id(self, port_id):
        return self._port_dic[port_id].get_pc_id()

    def find_mac(self, mac):
        return N9neighbour.find_mac(mac=mac, nei_lst=self._neigh_lst)

    def handle_port(self, pc_id, port_id, port_name, port_mode, vlans):
        try:
            port = self._port_dic[port_id]
            port.handle(pc_id=pc_id, port_name=port_name, port_mode=port_mode, vlans=vlans)
        except KeyError:
            raise ValueError('{}: does not have port "{}", check your configuration'.format(self._n9, port_id))

    def handle_pc(self, pc_id, pc_name, pc_mode):
        cmd_make = ['conf t', 'int ' + pc_id, 'desc ' + pc_name, 'mode ' + pc_mode]
        cmd_name = ['conf t', 'int ' + pc_id, 'desc ' + pc_name]
        cmd_mode = ['conf t', 'int ' + pc_id, 'mode ' + pc_mode]
        try:
            a_name = self._pc_dic[pc_id].get_name()
            self.fix_problem(cmd=cmd_name, msg='{} has actual description "{}" while requested is "{}"'.format(pc_id, a_name, pc_name))
            a_mode = self._pc_dic[pc_id].get_mode()
            if a_mode != pc_mode:
                self.fix_problem(cmd=cmd_mode, msg='{} has actual mode "{}" while requested is "{}"'.format(pc_id, a_mode, pc_mode))
        except KeyError:
            self.fix_problem(cmd=cmd_make, msg='no port-channel "{}"'.format(pc_id))

        # actual = self.n9_show_all()
        # for port_id in port_ids:
        #     self.n9_configure_port(pc_id=pc_id, port_id=port_id, vlans_string=vlans_string, desc=desc, mode=mode)
        #
        # actual_port_ids = actual['ports'].get(str(pc_id), [])
        # if actual_port_ids:  # port channel with this id already exists
        #     if port_ids != actual_port_ids:  # make sure that requested list of port-ids equals to actual list
        #         raise RuntimeError('{}: port-channel {} has different list of ports ({}) then requested ({})'.format(self, pc_id, actual_port_ids, port_ids))
        #     self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'switchport {} vlan {}'.format('trunk allowed' if mode == 'trunk' else 'access', vlans_string)])
        # else:  # port channel is not yet created
        #     self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'descr {0}'.format(desc), 'switchport', 'switchport mode ' + mode, 'switchport {} vlan {}'.format('trunk allowed' if mode == 'trunk' else 'access',
        #                                                                                                                                                                 vlans_string)])
        #
        #     if is_peer_link_pc:
        #         self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'vpc peer-link'], timeout=180)
        #     else:
        #         self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'spanning-tree port type edge {}'.format('trunk' if mode == 'trunk' else ''), 'shut', 'no lacp suspend-individual', 'no shut'], timeout=180)
        #
        #     for port_id in port_ids:  # add ports to the port-channel
        #         self.cmd(['conf t', 'int ethernet ' + port_id, 'channel-group {0} force mode active'.format(pc_id)])

    def handle_vlan(self, vlan_id, vlan_name):
        cmd = N9Vlan.get_cmd(vlan_id=vlan_id, vlan_name=vlan_name)
        try:
            actual_name = self._vlans[vlan_id].get_name()
            if actual_name != vlan_name:
                self.fix_problem(cmd=cmd, msg='vlan {} has actual name {} while requested is {}'.format(vlan_id, actual_name, vlan_name))
        except KeyError:
            self.fix_problem(cmd=cmd, msg='no vlan {}'.format(vlan_id, ' '.join(cmd)))

    def cleanup(self):
        del_vlan_interfaces = ['no int ' + x for x in self._vlan_port_dic.keys()]
        del_port_channels = ['no int ' + x for x in self._pc_dic.keys()]

        vlan_ids = set(self._vlans.keys()) - {'1'}
        del_vlans = ['no vlan ' + ','.join(vlan_ids[i:i + 64]) for i in range(0, len(vlan_ids), 64)]  # need to slice since no more then 64 ids allowed per operation
        del_vpc_domain = ['no vpc domain ' + self._vpc_domain.get_id()] if self._vpc_domain and self._vpc_domain.is_configured() else []

        last_port_id = max(map(lambda name: 0 if 'Ethernet' not in name else int(name.split('/')[-1]), self._port_dic.keys()))
        reset_ports = ['default int e 1/1-' + str(last_port_id)]
        self._n9.n9_cmd(['conf t'] + del_vlan_interfaces + del_port_channels + del_vlans + del_vpc_domain + reset_ports, timeout=60)

    def fix_problem(self, cmd, msg):
        from fabric.operations import prompt
        import time

        self._n9.log('{} do: {}'.format(msg, ' '.join(cmd)))
        time.sleep(1)  # prevent prompt message interlacing with log output
        if prompt('say y if you want to fix it: ') == 'y':
            self._n9.n9_cmd(cmd)


class Nexus(LabNode):
    def __init__(self, **kwargs):
        super(Nexus, self).__init__(**kwargs)
        self.__requested_topology = None

    @property
    def _requested_topology(self):
        if self.__requested_topology is None:
            self.__requested_topology = self.prepare_topology()
        return self.__requested_topology

    def get_pcs_to_fi(self):
        """Returns a list of pcs used on connection to peer N9K and both FIs"""
        return set([str(x.get_pc_id()) for x in self._wires if x.is_n9_fi()])

    def get_peer_link_wires(self):
        return [x for x in self._wires if x.is_n9_n9()]

    def get_peer_link_id(self):
        return self.get_peer_link_wires()[0].get_pc_id()

    def get_peer_linked_n9k(self):
        return self.get_peer_link_wires()[0].get_peer_node(self)

    def n9_allow_feature_nxapi(self):
        from fabric.api import settings, run

        oob_ip, oob_u, oob_p = self.get_oob()
        with settings(host_string='{user}@{ip}'.format(user=oob_u, ip=oob_ip), password=oob_p):
            if 'disabled'in run('sh feature | i nxapi', shell=False):
                run('conf t ; feature nxapi', shell=False)

    def _rest_api(self, commands, timeout=5, method='cli'):
        import requests
        import json

        oob_ip, oob_u, oob_p = self.get_oob()
        body = [{"jsonrpc": "2.0", "method": method, "params": {"cmd": x, "version": 1}, "id": i} for i, x in enumerate(commands, start=1)]
        url = 'http://{0}/ins'.format(oob_ip)
        try:
            data = json.dumps(body)
            result = requests.post(url, auth=(oob_u, oob_p), headers={'content-type': 'application/json-rpc'}, data=data, timeout=timeout)
            if result.ok:
                return result.json()
            else:
                raise RuntimeError('{}: {} {} {}'.format(self, url, body, result.text))

        except requests.exceptions.ConnectionError:
            self.n9_allow_feature_nxapi()
            return self._rest_api(commands=commands, timeout=timeout)
        except requests.exceptions.ReadTimeout:
            raise RuntimeError('{}: timed out after {} secs'.format(self, timeout))

    def n9_cmd(self, commands, timeout=5):
        d = {}
        if type(commands) is not list:
            is_not_list = True
            commands = [commands]
        else:
            is_not_list = False
        self.log('executing ' + ' '.join(commands))
        results = self._rest_api(commands=[commands] if type(commands) is not list else commands, timeout=timeout)
        if is_not_list:
            results = [results]
        for c, r in zip(commands, results):
            if 'result' not in r or r['result'] is None:
                d[c] = []
            else:
                r = r['result']['body']
                d[c] = r.values()[0].values()[0] if len(r) == 1 else r
        return d

    def get_actual_hostname(self):
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

    def n9_show_all(self):
        return N9Status(n9=self)

    def n9_validate(self):
        a = self.n9_show_all()
        for req_vlan_id, req_vlan_name in self._requested_topology['vlans'].items():
            a.handle_vlan(vlan_id=req_vlan_id, vlan_name=req_vlan_name)

        for req_vpc_id, req_vpc in self._requested_topology['vpc'].items():
            if req_vpc_id == 'mgmt0':  # it's a special mgmt port which is connected to OOB switch
                continue
            req_vpc_desc = '{} {}'.format(req_vpc['peer-node'], ' '.join(req_vpc['peer-ports']))
            for req_port_id in req_vpc['ports']:  # first check physical ports participating in this (v)PC
                a.handle_port(port_id=req_port_id, port_name=req_vpc_desc)

            a.handle_pc(pc_id=req_vpc_id, pc_name=req_vpc_desc, pc_mode=req_vpc['mode'])

        self.log(60 * '-')

    def n9_create_vpc(self, pc_id):
        if str(pc_id) not in self.n9_show_vpc():
            self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'vpc {0}'.format(pc_id)], timeout=60)

    def n9_configure_vxlan(self, asr_port):
        import re

        number_in_node_id = map(int, re.findall(r'\d+', self.get_node_id()))[0]
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

    def n9_add_vlan_range(self, interfaces):
        vlan_range = self.lab().get_vlan_range().replace(':', '-')
        commands = ['conf t', 'vlan {0}'.format(vlan_range), 'no shut', 'exit', 'int e{0}'.format(',e'.join(interfaces)), 'switchport trunk allowed vlan add {0}'.format(vlan_range), 'end']
        self.cmd(commands)

    # def n9_configure_peer_link(self):
    #     peer_link = self._requested_topology['peer-link']
    #     ip = peer_link['ip']
    #     if ip:
    #         pc_id = peer_link['pc-id']
    #         desc = peer_link['description']
    #         port_ids = peer_link['ports']
    #         vlans_string = peer_link['vlans']
    #         self.n9_configure_vpc_domain(peer_ip=ip)
    #         self.n9_create_port_channel(pc_id=pc_id, desc=desc, port_ids=port_ids, vlans_string=vlans_string, mode='trunk', is_peer_link_pc=True)

    # def n9_configure_vpc(self):
    #     vpc = self._requested_topology['vpc']
    #     for pc_id, info in vpc.items():
    #         self.n9_create_port_channel(pc_id=pc_id, desc=info['description'], port_ids=info['ports'], mode=info['mode'], vlans_string=info['vlans'])
    #         if self.get_peer_link_wires():
    #             self.n9_create_vpc(pc_id)

    def prepare_topology(self):
        topo = {'vpc': {}, 'vlans': {}, 'peer-link': {'description': 'peerlink', 'ip': None, 'vlans': [], 'ports': []}}

        for wire in self.get_all_wires():
            own_port_id = wire.get_own_port(self)
            peer_port_id = wire.get_peer_port(self)
            pc_id = wire.get_pc_id() or own_port_id
            if wire.is_n9_n9():
                mode = 'trunk'
                vlan_ids = []  # vlans for peerlink will be collected later in this method
            elif wire.is_n9_tor():
                vlan_ids = []  # vlans for uplink will be collected later in this method
                mode = 'trunk'
            elif wire.is_n9_pxe():
                vlan_ids = ['1']
                mode = 'access'
            elif wire.is_n9_fi():
                mode = 'trunk'
                vlan_ids = []
            elif wire.is_n9_ucs():
                vlan_ids = sorted(set([x.get_vlan_id() for x in wire.get_nics()]))
                mode = 'trunk' if 'MLOM' in peer_port_id else 'access'
            elif wire.is_n9_oob():
                vlan_ids = []
                mode = None
            else:
                raise ValueError('{}:  strange wire which should not go to N9K: {}'.format(self, wire))
            topo['vpc'].setdefault(pc_id, {'peer-node': wire.get_peer_node(self), 'pc-id': pc_id, 'vlans': vlan_ids, 'ports': [], 'peer-ports': [], 'mode': mode})
            topo['vpc'][pc_id]['ports'].append(own_port_id)
            topo['vpc'][pc_id]['peer-ports'].append(peer_port_id)
        vlan_id_vs_net = {net.get_vlan_id(): net for net in self.lab().get_all_nets().values()}
        for vlan_id in sorted(set(reduce(lambda lst, a: lst + a['vlans'], topo['vpc'].values(), []))):  # all vlans seen on all wires
            topo['vlans'][vlan_id] = str(self.lab()) + '-' + vlan_id_vs_net[vlan_id].get_net_id()  # fill vlan_id vs vlan name section
            if 'peerlink' in topo['vpc']:
                topo['vpc']['peerlink']['vlans'].append(vlan_id)
            if 'uplink' in topo['vpc'] and vlan_id_vs_net[vlan_id].is_via_tor():
                topo['vpc']['uplink']['vlans'].append(vlan_id)
        return topo

    def n9_configure_asr1k(self):
        self.cmd(['conf t', 'int po{0}'.format(self.get_peer_link_id()), 'shut'])
        asr = filter(lambda x: x.is_n9_asr(), self._wires)
        self.n9_configure_vxlan(asr[0].get_own_port(self))

    def n9_cleanup(self):
        self.n9_show_all().cleanup()

    def n9_show_bgp_l2vpn_evpn(self):
        return self.cmd('sh bgp l2vpn evpn')

    def n9_show_bgp_sessions(self):
        return self.cmd('sh bgp sessions')

    def n9_show_bgp_all(self):
        return self.cmd('sh bgp all')

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

    def n9_show_lldp_neighbor(self):
        self.cmd(['conf t', 'feature lldp'])
        lldp_neis = self.cmd(['sh lldp nei det'])
        return lldp_neis['result']['body']['TABLE_nbor_detail']['ROW_nbor_detail']

    def n9_show_l2route_evpn_mac_all(self):
        return self.cmd(' sh l2route evpn mac all')

    def n9_show_users(self):
        res = self.cmd(['show users'])
        if res == 'timeout':
            return []
        if res['result']:
            return res['result']['body']['TABLE_sessions']['ROW_sessions']
        else:
            return []  # no current session

    def n9_show_nve_peers(self):
        r = self.cmd('sh nve peers')
        return r['result']['body']['TABLE_nve_peers']['ROW_nve_peers'] if r['result'] else {}

    def r_collect_config(self):
        return self._format_single_cmd_output(cmd='show running config', ans=self.n9_show_running_config())


class VimTor(Nexus):
    def r_border_leaf(self):
        vlans = self._requested_topology['vlans']
        tenant_vlan_ids = [vlan_id for vlan_id, name_and_others in vlans.items() if name_and_others['name'] == '{}-t'.format(self.pod)]
        if not tenant_vlan_ids:
            return  # this switch has no tenant vlan so do not configure border leaf on it

        tenant_vlan_id = tenant_vlan_ids[0]
        this_switch_bgp_nei_ip = '34.34.34.{}'.format(self._n)
        loopback_ip = '90.90.90.90'
        xrvr_bgp_ips = ['34.34.34.101', '34.34.34.102']
        self.cmd(['conf t', 'interface Vlan{}'.format(tenant_vlan_id), 'no shut', 'ip address {}/24'.format(this_switch_bgp_nei_ip), 'no ipv6 redirects', 'ip router ospf 100 area 0.0.0.0', 'hsrp 34 ', 'ip 34.34.34.100'],
                 timeout=60)
        self.cmd(['conf t', 'interface loopback0', 'ip address {}/32'.format(loopback_ip), 'ip address 92.92.92.92/32 secondary', 'ip router ospf 100 area 0.0.0.0'], timeout=60)
        self.cmd(['conf t', 'router ospf 100', 'router-id {}'.format(this_switch_bgp_nei_ip), 'area 0.0.0.0 default-cost 10'], timeout=60)
        self.cmd(['conf t', 'router bgp 23', 'router-id {}'.format(this_switch_bgp_nei_ip), 'address-family ipv4 unicast', 'address-family l2vpn evpn', 'retain route-target all',
                  'neighbor {}'.format(xrvr_bgp_ips[0]), 'remote-as 23', 'update-source Vlan{}'.format(tenant_vlan_id), 'address-family l2vpn evpn', 'send-community both',
                  'neighbor {}'.format(xrvr_bgp_ips[1]), 'remote-as 23', 'update-source Vlan{}'.format(tenant_vlan_id), 'address-family l2vpn evpn', 'send-community both'], timeout=60)


class VimCatalist(Nexus):
    pass