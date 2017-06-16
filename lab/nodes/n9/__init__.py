from lab.nodes import LabNode


class N9(LabNode):
    def __init__(self, **kwargs):
        super(N9, self).__init__(**kwargs)
        self.__requested_topology = None
        self._ports = None
        self._port_channels = None
        self._vlans = None
        self._neighbours = None
        self._vpc_domain = None

    @property
    def ports(self):
        if not self._ports:
            self.n9_get_status()
        return self._ports

    @property
    def port_channels(self):
        if not self._port_channels:
            self.n9_get_status()
        return self._port_channels

    @property
    def neighbours(self):
        if not self._neighbours:
            self.n9_get_status()
        return self._neighbours

    @property
    def vlans(self):
        if not self._vlans:
            self.n9_get_status()
        return self._vlans

    @property
    def vpc_domain(self):
        if self._vlans is None:
            self.n9_get_status()
        return self._vpc_domain

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

    def find_neighbour_with_mac(self, mac):
        from lab.nodes.n9.n9_neighbour import N9neighbour

        return N9neighbour.find_with_mac(mac=mac, neighbours=self.neighbours)

    def n9_change_port_state(self, port_no, port_state="no shut"):
        """
        Change port state of the port
        :param port_no: should be in full format like e1/3 or po1
        :param port_state: 'shut' or 'no shut'
        """
        self.cmd(['conf t', 'int {}'.format(port_no), port_state])

    def n9_get_status(self):
        from lab.nodes.n9.n9_neighbour import N9neighbour
        from lab.nodes.n9.n9_port import N9Port
        from lab.nodes.n9.n9_port_channel import N9PortChannel
        from lab.nodes.n9.n9_vpc_domain import N9VpcDomain
        from lab.nodes.n9.n9_vlan import N9Vlan
        from lab.nodes.n9.n9_vlan_port import N9VlanPort

        a = self.n9_cmd(['sh port-channel summary', 'sh int st', 'sh int br', 'sh vlan', 'sh cdp nei det', 'sh lldp nei det'] + (['sh vpc'] if self.id != 'n9n' else []), timeout=30)

        self._port_channels = N9PortChannel.process_n9_answer(n9=self, answer=a['sh port-channel summary'])
        vpc_domain, vpc_dic = N9VpcDomain.process_n9_answer(n9=self, answer=a['sh vpc']) if 'sh vpc' in a else None, {}
        map(lambda vpc_id, vpc: self.port_channels[vpc_id].update(vpc), vpc_dic.items())

        self._ports = {}
        for st, br in zip(a['sh int st'], a['sh int br']):
            st.update(br)  # combine both since br contains pc info
            port_id = st['interface']
            if port_id.startswith('port-channel'):
                self._port_channels[port_id].update(st)
            elif port_id.startswith('Vlan'):
                self._ports[port_id] = N9VlanPort(n9=self, n9_dict=st)
            elif port_id.startswith('Ethernet'):
                self._ports[port_id] = N9Port(n9=self, n9_dic=st, pc_dic=self._port_channels)
            else:
                continue
        self._neighbours = N9neighbour.process_n9_answer(n9=self, answer=a['sh lldp nei det'])
        self._neighbours.extend(N9neighbour.process_n9_answer(n9=self, answer=a['sh cdp nei det']))
        self._vlans = N9Vlan.process_n9_answer(n9=self, answer=a['sh vlan'])

    def n9_validate(self):
        from lab.nodes.n9.n9_vlan import N9Vlan

        for req_vlan_id, req_vlan_name in self._requested_topology['vlans'].items():
            self.vlans.get(req_vlan_id, N9Vlan.create(n9=self, vlan_id=req_vlan_id)).handle_vlan(vlan_id=req_vlan_id, vlan_name=req_vlan_name)

        for req_vpc_id, req_vpc in self._requested_topology['vpc'].items():
            if req_vpc_id == 'mgmt0':  # it's a special mgmt port which is connected to OOB switch
                continue
            req_vpc_desc = '{} {}'.format(req_vpc['peer-node'], ' '.join(req_vpc['peer-ports']))
            for req_port_id in req_vpc['ports']:  # first check physical ports participating in this (v)PC
                self.ports[req_port_id].handle_port(port_name=req_vpc_desc)

            self.port_channels[req_vpc_id].handle_pc(pc_name=req_vpc_desc, pc_mode=req_vpc['mode'])

        self.log(60 * '-')

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
        vlan_id_vs_net = {net.get_vlan_id(): net for net in self.pod.networks.values()}
        for vlan_id in sorted(set(reduce(lambda lst, a: lst + a['vlans'], topo['vpc'].values(), []))):  # all vlans seen on all wires
            topo['vlans'][vlan_id] = str(self.pod) + '-' + vlan_id_vs_net[vlan_id].get_net_id()  # fill vlan_id vs vlan name section
            if 'peerlink' in topo['vpc']:
                topo['vpc']['peerlink']['vlans'].append(vlan_id)
            if 'uplink' in topo['vpc'] and vlan_id_vs_net[vlan_id].is_via_tor():
                topo['vpc']['uplink']['vlans'].append(vlan_id)
        return topo

    def n9_configure_asr1k(self):
        self.cmd(['conf t', 'int po{0}'.format(self.get_peer_link_id()), 'shut'])
        asr = filter(lambda x: x.is_n9_asr(), self._wires)
        self.n9_configure_vxlan(asr[0].get_own_port(self))

    def cleanup(self):
        del_vlan_interfaces = ['no int ' + x for x in self.ports.keys() if x.startswith('Vlan')]
        del_port_channels = ['no int ' + x for x in self.port_channels.keys()]

        vlan_ids = set(self._vlans.keys()) - {'1'}
        del_vlans = ['no vlan ' + ','.join(vlan_ids[i:i + 64]) for i in range(0, len(vlan_ids), 64)]  # need to slice since no more then 64 ids allowed per operation
        del_vpc_domain = ['no vpc domain ' + self.vpc_domain.domain_id] if self.vpc_domain.is_configured else []

        last_port_id = max(map(lambda name: 0 if 'Ethernet' not in name else int(name.split('/')[-1]), self.ports.keys()))
        reset_ports = ['default int e 1/1-' + str(last_port_id)]
        self.n9_cmd(['conf t'] + del_vlan_interfaces + del_port_channels + del_vlans + del_vpc_domain + reset_ports, timeout=60)

    def n9_show_bgp_l2vpn_evpn(self):
        return self.cmd('sh bgp l2vpn evpn')

    def n9_show_bgp_sessions(self):
        return self.cmd('sh bgp sessions')

    def n9_show_bgp_all(self):
        return self.cmd('sh bgp all')

    def n9_show_running_config(self):
        return self.cmd(commands=['sh run'], method='cli_ascii')['result']['msg']

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


class VimCat(N9):
    pass
