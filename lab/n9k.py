from lab.lab_node import LabNode


class Nexus(LabNode):

    def __repr__(self):
        return u'{0} {1}'.format(self.lab(), self.name())

    def get_pcs_for_n9_and_fi_and_tor(self):
        """Returns a list of pcs used on connection to peer N9K and both FIs"""
        wires = self.get_wires_for_n9_and_fi_and_tor()
        return sorted(set([x.get_pc_id() for x in wires]))

    def get_wires_for_n9_and_fi_and_tor(self):
        """Returns a list of wires used on connection to peer N9K and both FIs"""
        wires = filter(lambda w: w.is_n9_n9() or w.is_n9_fi() or w.is_n9_tor(), self._downstream_wires + self._upstream_wires)
        return wires

    def get_wires_to_servers(self):
        """Returns a list wires connected servers"""
        return filter(lambda w: w.is_n9_ucs(), self._downstream_wires)

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
        except requests.exceptions.ReadTimeout:
            return 'timeout' if len(commands) == 1 else ['timeout'] * len(commands)

    def get_hostname(self):
        res = self.cmd(['sh switchname'])
        return res['result']['body']['hostname']

    def cmd(self, commands, timeout=15):
        if isinstance(commands, basestring):  # it might be provided as a string where commands are separated by ','
            commands = commands.strip('[]')
            commands = commands.split(',')

        results = self._rest_api(commands=commands, timeout=timeout)
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
        if res == 'timeout':
            return []
        return [x['port-channel'] for x in res['result']['body']['TABLE_channel']['ROW_channel']]

    def show_interface_switchport(self, name):
        res = self.cmd(['show interface {0} switchport'.format(name)])
        if res == 'timeout':
            return []
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
        pcs = self.cmd(['sh port-channel summary'])
        if pcs['result']:
            pcs = pcs['result']['body'][u'TABLE_channel'][u'ROW_channel']
            # if there is only one port-channel the API returns object but not a list. Convert to list
            pcs = [pcs] if isinstance(pcs, dict) else pcs
            return pcs

    def delete_port_channels(self, skip_list=None):
        skip_list = skip_list or []

        pcs = self.show_port_channels()
        if not pcs:
            return
        pc_ids = [pc['group'] for pc in pcs if int(pc['group']) not in skip_list]
        for pc_id in pc_ids:
            # delete all port-channels
            self.cmd(['conf t', 'no int port-channel {0}'.format(pc_id)])

    def create_port_channel(self, pc_id, pc_name, ports, speed, vlans):
        """
        For example arguments: 2, ['1/2', '1/10'], [222, 333]
        :param pc_name:
        :param vlans:
        :param speed:
        :param ports:
        :param pc_id:
        :return:
        """
        # create port channel
        vlans_string = ','.join(map(lambda x: str(x), vlans))
        self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'description {0}'.format(pc_name), 'switchport', 'switchport mode trunk', 'switchport trunk allowed vlan {0}'.format(vlans_string),
                  'speed {0}'.format(speed)])
        # add ports to the port-channel
        for port in ports:
            self.cmd(['conf t', 'int ethernet ' + port, 'description {0}'.format(pc_name), 'switchport', 'switchport mode trunk', 'switchport trunk allowed vlan {0}'.format(vlans_string),
                      'speed {0}'.format(speed), 'channel-group {0} mode active'.format(pc_id)])

    def create_vpc(self, pc_id):
        self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'vpc {0}'.format(pc_id)])

    def create_vpc_peer_link(self, pc_id):
        self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'vpc peer-link'])

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

    def assign_vlans(self, int_name, port, vlans):
        self.cmd(['conf t', 'int e{0}'.format(port), 'description {0}'.format(int_name), 'switchport trunk allowed vlan {0}'.format(','.join([str(x) for x in vlans]))])

    def configure_vxlan(self, asr_port):
        # Configure vxlan artefacts

        lo1_ip = '1.1.1.22{0}'.format(self.index())
        lo2_ip = '2.2.2.22{0}'.format(self.index())
        router_ospf = '111'
        router_area = '0.0.0.0'
        eth48_ip = '169.0.{0}.1'.format(self.index())
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
        old_vpc_domain = self.cmd(['sh vpc'])['result']['body']['vpc-domain-id']
        if old_vpc_domain != 'not configured':
            self.cmd(['conf t', 'no vpc domain {0}'.format(old_vpc_domain)])
        self.cmd(['conf t', 'feature vpc'])
        self.cmd(['conf t', 'vpc domain {0}'.format(domain_id), 'peer-keepalive destination {0}'.format(peer_ip)])

    def get_peer_link_id(self):
        return self._peer_link_wires[0].get_pc_id().split('-')[0]

    def configure_for_osp7(self, topology):
        from lab.logger import lab_logger
        lab_logger.info('Configuring {0}'.format(self))

        self.cmd(['conf t', 'feature lacp'])
        self.delete_port_channels()
        self.delete_vlans()

        vlans = ', '.join(map(lambda x: str(x), self.lab().get_all_vlans()))
        self.cmd(['conf t', 'vlan {0}'.format(vlans), 'no shut'])

        peer = self._peer_link_wires[0].get_peer_node(self)
        ip, _, _, _ = peer.get_ssh()
        self.configure_vpc_domain(peer_ip=ip)

        pc_id_versus_ports = {}
        for w in self._peer_link_wires + self._downstream_wires + self._upstream_wires:
            pc_id = w.get_pc_id()
            pc_id_versus_ports.setdefault(pc_id, [])
            pc_id_versus_ports[pc_id].append(w.get_own_port(self))

        for pc_id, ports in pc_id_versus_ports.iteritems():
            if 'tor' in pc_id:
                vlans = self.lab().get_net_vlans('user')
            elif 'cobbler' in pc_id:
                vlans = self.lab().get_net_vlans('pxe-ext')
            elif 'asr' in pc_id:
                continue
            else:
                vlans = self.lab().get_all_vlans()

            if pc_id[0].isdigit():
                is_peer = 'peer' in pc_id
                try:
                    pc_id, pc_name = pc_id.split('-')
                except ValueError:
                    raise ValueError('Expected pc_id in form ID-NODE_NAME. Provided: {0}'.format(pc_id))
                self.create_port_channel(pc_id=pc_id, pc_name=pc_name, ports=ports, vlans=vlans, speed=10000)
                if is_peer:
                    self.create_vpc_peer_link(pc_id)
                else:
                    self.create_vpc(pc_id)
            else:
                self.assign_vlans(int_name=pc_id, port=ports[0], vlans=vlans)

        if topology == self.lab().TOPOLOGY_VXLAN:
            self.cmd(['conf t', 'int po{0}'.format(self.get_peer_link_id()), 'shut'])
            asr = filter(lambda x: x.is_n9_asr(), self._upstream_wires)
            self.configure_vxlan(asr[0].get_own_port(self))
