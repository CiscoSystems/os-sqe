from lab.lab_node import LabNode


class Nexus(LabNode):

    def __repr__(self):
        return u'{0} {1}'.format(self.lab(), self.name())

    def id_to_int(self, id):
        try:
            return int(id)
        except ValueError:
            # Skip the wire because port-channel id is not an integer value
            return None

    def get_pcs_for_n9_and_fi_and_tor(self):
        """Returns a list of pcs used on connection to peer N9K and both FIs"""
        wires = self.get_wires_for_n9_and_fi_and_tor()
        return sorted(set([x.get_pc_id() for x in wires]))

    def get_wires_for_n9_and_fi_and_tor(self):
        """Returns a list of wires used on connection to peer N9K and both FIs"""
        wires = filter(lambda w: w.is_n9_n9() or w.is_n9_fi() or w.is_n9_tor(), self._downstream_wires + self._upstream_wires)
        return wires

    def get_wires_for_n9_and_n9(self):
        """Returns a list of wires used on connection to peer N9K"""
        wires = filter(lambda w: w.is_n9_n9(), self._downstream_wires + self._upstream_wires)
        return wires

    def get_peer(self):
        wires = self.get_wires_for_n9_and_n9()
        peer = wires[0]._node_N if wires[0]._node_S == self else wires[0]._node_S
        return peer

    def get_pcs_for_n9(self):
        """Returns a list of wires used on connection to peer N9K"""
        wires = filter(lambda w: w.is_n9_n9(), self._upstream_wires)
        return sorted(set([x.get_pc_id() for x in wires]))

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
        return res[0]['result']['body']['hostname']

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
        return results

    def change_port_state(self, port_no, port_state="no shut"):
        """
        Change port state of the port
        :param port_no: should be in full format like e1/3 or po1
        :param port_state: 'shut' or 'no shut'
        """
        self.cmd(['conf t', 'int {port}'.format(port=port_no), '{0}'.format(port_state)])

    def show_port_channel_summary(self):
        res = self.cmd(['show port-channel summary'])
        if res[0] == 'timeout':
            return []
        return [x['port-channel'] for x in res[0]['result']['body']['TABLE_channel']['ROW_channel']]

    def get_pc_for_osp(self):
        res = self.cmd(['show port-channel summary'], timeout=15)
        if res[0] == 'timeout':
            raise Exception('Connection to N9K {ip} timed out.'.format(ip=self.ip))
        pc = []
        try:
            all_pc_w_ports = [x for x in res[0]['result']['body']['TABLE_channel']['ROW_channel'] if 'TABLE_member' in x]
            for entry in all_pc_w_ports:
                ports = entry['TABLE_member']['ROW_member']
                if isinstance(ports, list):
                    port_list = set([x['port'].split('Ethernet')[1] for x in ports])
                    if port_list.issubset(self.osp_ports):
                        pc.append(entry['port-channel'])
                else:
                    port = ports['port']
                    if port.split('Ethernet')[1] in self.osp_ports:
                         pc.append(entry['port-channel'])
        except Exception:
            raise Exception('Error in parsing response from N9K {ip}. Response: {res}'.format(ip=self._ip, res=res))
        return pc

    def show_interface_switchport(self, name):
        res = self.cmd(['show interface {0} switchport'.format(name)])
        if res[0] == 'timeout':
            return []
        vlans_str = res[0]['result']['body']['TABLE_interface']['ROW_interface']['trunk_vlans']
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
        if pcs[0]['result']:
            pcs = pcs[0]['result']['body'][u'TABLE_channel'][u'ROW_channel']
            # if there is only one port-channel the API returns object but not a list. Convert to list
            pcs = [pcs] if isinstance(pcs, dict) else pcs
            return pcs

    def delete_port_channels(self, skip_list=None):
        skip_list = skip_list or []

        pcs = self.show_port_channels()
        pc_ids = [pc['group'] for pc in pcs if int(pc['group']) not in skip_list]
        for pc_id in pc_ids:
            # delete all port-channels
            self.cmd(['conf t', 'no int port-channel {0}'.format(pc_id)])

    def create_port_channels(self, pc_id, ports, vlans):
        """
        For example arguments: 2, ['1/2', '1/10'], [222, 333]
        :return:
        """
        self.cmd(['conf t', 'int port-channel {0}'.format(pc_id),
                  'switchport', 'switchport mode trunk', 'switchport trunk allowed vlan none',
                  'speed 10000', 'feature lacp'])
        # Add vlans to allowed vlans list
        self.cmd(['conf t', 'int port-channel {0}'.format(pc_id),
                  'switchport trunk allowed vlan add {0}'.format(','.join(vlans))])
        # Add ports to the port-channel
        for port in ports:
            self.cmd(['conf t', 'int ethernet ' + port, 'switchport', 'switchport mode trunk',
                  'switchport trunk allowed vlan {0}'.format(','.join(vlans)), 'speed 10000',
                  'channel-group {0} mode active'.format(pc_id)])

    def show_vlans(self):
        vlans = self.cmd(['sh vlan'])
        if vlans[0]['result']:
            vlans = vlans[0]['result']['body'][u'TABLE_vlanbrief'][u'ROW_vlanbrief']
            vlans = [vlans] if isinstance(vlans, dict) else vlans
            return vlans

    def show_cdp_neighbor(self):
        cdp_neis = self.cmd(['sh cdp nei det'])
        return cdp_neis[0]['result']['body']['TABLE_cdp_neighbor_detail_info']['ROW_cdp_neighbor_detail_info']

    def show_users(self):
        res = self.cmd(['show users'])
        if res[0] == 'timeout':
            return []
        if res[0]['result']:
            return res[0]['result']['body']['TABLE_sessions']['ROW_sessions']
        else:
            return []  # no current session

    def delete_vlans(self):
        vlans = self.show_vlans()
        vlans_str = ','.join([v['vlanshowbr-vlanid-utf'] for v in vlans])
        self.cmd(['conf t', 'no vlan {0}'.format(vlans_str)])

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
        old_vpc_domain = self.cmd(['sh vpc'])[0]['result']['body']['vpc-domain-id']
        if old_vpc_domain != 'not configured':
            self.cmd(['conf t', 'no vpc domain {0}'.format(old_vpc_domain)])
        self.cmd(['conf t', 'feature vpc'])
        self.cmd(['conf t', 'vpc domain {0}'.format(domain_id), 'peer-keepalive destination {0}'.format(peer_ip)])

    def configure_for_osp7(self):

        ports_n9k = []
        ports_fi_a = []
        ports_fi_b = []
        ports_tor = []

        for nei in self.show_cdp_neighbor():
            port_id = nei['intf_id']
            if 'TOR' in nei['device_id']:
                ports_tor.append(port_id)
            if 'UCS-FI' in nei['platform_id']:
                if not filter(lambda w: w._port_N in port_id, self._downstream_wires):
                    raise Exception('Port %s is not described in lab config. It is connected to FI'.format(port_id))
                if '-A' in nei['device_id']:
                    ports_fi_a.append(port_id)
                if '-B' in nei['device_id']:
                    ports_fi_b.append(port_id)
            if 'N9K' in nei['platform_id']:
                if not filter(lambda w: w._port_N in port_id, self.get_all_wires()):
                    raise Exception('Port {0} is not described in lab config. It is connected to other N9k'.format(port_id))
                ports_n9k.append(port_id)

        # Delete port channels
        self.delete_port_channels()

        # Delete vlans
        self.delete_vlans()

        # Create vlans
        n9k_vlans = []
        for net_name, vlans in self.lab()._net_vlans.iteritems():
            vlans_str = [str(v) for v in vlans]
            n9k_vlans = n9k_vlans + vlans_str
            self.cmd(['conf t', 'vlan {0}'.format(', '.join(vlans_str)), 'no shut'])

        # Configure VPC domain
        self.configure_vpc_domain(peer_ip=self.get_peer()._ip)

        # Create port-channels
        for w in self.get_wires_for_n9_and_fi_and_tor():
            self.create_port_channels(w.get_pc_id(), [w.get_port_n()], n9k_vlans)

        # Configure VPCs
        processed_pcs = set()
        for wire in self.get_wires_for_n9_and_fi_and_tor():
            pc_id = self.id_to_int(wire.get_pc_id())
            if pc_id not in processed_pcs:
                if wire.is_n9_n9():
                    # Peer-link VPC
                    self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'vpc peer-link'])
                else:
                    # Other VPCs
                    self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'vpc {0}'.format(pc_id)])
                processed_pcs.add(pc_id)

        # Looks for ports connected to ASR. If at least one exists then configure VXLAN
        for w in self._upstream_wires:
            if w.is_n9_asr():
                self.configure_vxlan(w.get_port_s())
                break

