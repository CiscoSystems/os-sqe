from lab.nodes import LabNode


class N9(LabNode):
    def __init__(self, **kwargs):
        super(N9, self).__init__(**kwargs)
        self._ports = None
        self._port_channels = None
        self._vlans = None
        self._neighbours_lldp = None
        self._neighbours_cdp = None
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
    def neighbours_lldp(self):
        if not self._neighbours_lldp:
            self.n9_get_status()
        return self._neighbours_lldp

    @property
    def neighbours_cdp(self):
        if not self._neighbours_cdp:
            self.n9_get_status()
        return self._neighbours_cdp

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

    def n9_allow_feature_nxapi(self):
        from fabric.api import settings, run

        with settings(host_string='{user}@{ip}'.format(user=self.oob_username, ip=self.oob_ip), password=self.oob_password):
            if 'disabled'in run('sh feature | i nxapi', shell=False):
                run('conf t ; feature nxapi', shell=False)

    def _rest_api(self, commands, timeout=5, method='cli'):
        import requests
        import json

        body = [{"jsonrpc": "2.0", "method": method, "params": {"cmd": x, "version": 1}, "id": i} for i, x in enumerate(commands, start=1)]
        url = 'http://{0}/ins'.format(self.oob_ip)
        try:
            data = json.dumps(body)
            result = requests.post(url, auth=(self.oob_username, self.oob_password), headers={'content-type': 'application/json-rpc'}, data=data, timeout=timeout)
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

    def find_neighbour_with_mac(self, mac, cimc_port_id):
        from lab.nodes.n9.n9_neighbour import N9neighbourLLDP

        return N9neighbourLLDP.find_with_mac(mac=mac, cimc_port_id=cimc_port_id, neighbours=self.neighbours_lldp)

    def n9_change_port_state(self, port_no, port_state="no shut"):
        """
        Change port state of the port
        :param port_no: should be in full format like e1/3 or po1
        :param port_state: 'shut' or 'no shut'
        """
        self.cmd(['conf t', 'int {}'.format(port_no), port_state])

    def n9_get_status(self):
        from lab.nodes.n9.n9_neighbour import N9neighbourLLDP, N9neighbourCDP
        from lab.nodes.n9.n9_port import N9Port
        from lab.nodes.n9.n9_port_channel import N9PortChannel
        from lab.nodes.n9.n9_vlan import N9Vlan
        from lab.nodes.n9.n9_vlan_port import N9VlanPort

        a = self.n9_cmd(['sh port-channel summary', 'sh int st', 'sh int br', 'sh vlan', 'sh cdp nei det', 'sh lldp nei det'] + (['sh vpc'] if self.id != 'nc' else []), timeout=30)

        self._neighbours_lldp = N9neighbourLLDP.process_n9_answer(n9=self, answer=a['sh lldp nei det'])
        self._neighbours_cdp = N9neighbourCDP.process_n9_answer(n9=self, answer=a['sh cdp nei det'])

        self._vlans = N9Vlan.process_n9_answer(n9=self, answer=a['sh vlan'])

        if 'sh vpc' in a:
            peer_tbl = a['sh vpc'].get('TABLE_peerlink', {'ROW_peerlink': []})['ROW_peerlink']
            vpc_tbl = a['sh vpc'].get('TABLE_vpc', {'ROW_vpc': []})['ROW_vpc']
            vpc_lst = [vpc_tbl] if type(vpc_tbl) is dict else vpc_tbl  # if there is only one vpc the API returns dict but not a list. Convert to list
            sh_vpc_dics = {x['vpc-ifindex'].replace('Po', 'port-channel'): x for x in vpc_lst}
            assert len(sh_vpc_dics) == int(a['sh vpc']['num-of-vpcs'])  # this is a number of vpc excluding peer-link vpc
            if peer_tbl:
                sh_vpc_dics[peer_tbl['peerlink-ifindex'].replace('Po', 'port-channel')] = peer_tbl
        else:
           sh_vpc_dics = {}
        sh_pc_sum_lst = [a['sh port-channel summary']] if type(a['sh port-channel summary']) is dict else a['sh port-channel summary']  # if there is only one port-channel the API returns dict but not a list. Convert to list
        sh_pc_sum_dics = {x['port-channel']: x for x in sh_pc_sum_lst}

        self._ports = {}
        self._port_channels = {}
        for st, br in zip(a['sh int st'], a['sh int br']):
            port_id = st['interface']
            if port_id.startswith('port-channel'):
                self._port_channels[port_id] = N9PortChannel(n9=self, sh_int_st_dic=st, sh_int_br_dic=br, sh_pc_sum_dic=sh_pc_sum_dics[port_id], sh_vpc_dic=sh_vpc_dics.get(port_id))
            elif port_id.startswith('Vlan'):
                self._ports[port_id] = N9VlanPort(n9=self, sh_int_st_dic=st, sh_int_br_dic=br)
            elif port_id.startswith('Ethernet'):
                self._ports[port_id] = N9Port(n9=self, sh_int_st_dic=st, sh_int_br_dic=br)
            else:
                continue


    def n9_validate(self):
        from lab.nodes.n9.n9_vlan import N9Vlan
        from lab.nodes.n9.n9_port_channel import N9PortChannel
        from lab.nodes.n9.n9_port import N9Port

        map(lambda v: self.vlans.get(str(v.vlan), N9Vlan.create(n9=self, vlan_id=v.vlan)).handle_vlan(vlan_name=self.pod.name[:3] + '-' + v.id), self.pod.networks.values())

        for wire in [x for x in self.pod.wires if self in [x.n1, x.n2]]:
            own_port_id = wire.get_own_port(node=self)
            if wire.is_n9_ucs():  # it's a potential connection to our node
                desc = self.pod.name[:3] + ' '
                pc_id = '????'
                port_mode = 'access'
                vlans = 'alll'
            elif wire.is_n9_oob():
                continue
            elif wire.is_n9_n9():  # it's a potential peer link
                pc_id = wire.pc_id
                desc = 'peer-link'
                port_mode = 'trunk'
                vlans = 'all'
            elif wire.is_n9_tor():
                pc_id = '?????'
                desc = 'up link'
                port_mode = 'trunk'
                vlans = 'all'
            else:
                pc_id = None
                port_mode = None
                vlans = None
                desc = 'XXX'
            if pc_id:
                N9PortChannel.check_create(n9=self, pc_id=pc_id, desc=desc, mode=port_mode, vlans=vlans)
            self.ports[own_port_id].check(pc_id=pc_id, port_name=desc, port_mode=port_mode, vlans=vlans)

        self.log(60 * '-')

    def n9_fix_problem(self, cmd, msg):
        from fabric.operations import prompt
        import time

        self.log('{} do: {}'.format(msg, ' '.join(cmd)))
        time.sleep(1)  # prevent prompt message interlacing with log output
        if prompt('say y if you want to fix it: ') == 'y':
            self.n9_cmd(cmd)

    def n9_configure_vxlan(self, asr_port):
        import re

        number_in_node_id = map(int, re.findall(r'\d+', self.id))[0]
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
        return self.single_cmd_output(cmd='show running config', ans=self.n9_show_running_config())
