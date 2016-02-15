from lab.lab_node import LabNode


class Nexus(LabNode):

    def __repr__(self):
        return u'{0} {1}'.format(self.lab(), self.name())

    def get_pcs_for_n9_and_fi(self):
        """Returns a list of pcs used on connection to peer N9K and both FIs"""
        wires = filter(lambda w: w.is_n9_n9() or w.is_n9_fi(), self._downstream_wires + self._upstream_wires)
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

    def show_vlan(self):
        res = self.cmd(['show vlan'])
        if res[0] == 'timeout':
            return []
        vlans = [x['vlanshowbr-vlanname'] for x in res[0]['result']['body']['TABLE_vlanbrief']['ROW_vlanbrief']]
        return vlans

    def show_users(self):
        res = self.cmd(['show users'])
        if res[0] == 'timeout':
            return []
        if res[0]['result']:
            return res[0]['result']['body']['TABLE_sessions']['ROW_sessions']
        else:
            return []  # no current session

    def no_vlans(self, pattern):
        vlans = filter(lambda name: pattern in name, self.show_vlan())
        vlan_ids = [x.strip(pattern) for x in vlans]

        def chunks(l, n):
            """Yield successive chunks from list.
            :param n: size of the chunk
            :param l: list to be split
            """
            for i in xrange(0, len(l), n):
                yield l[i:i+n]

        for chunk in chunks(vlan_ids, 64):
            part_of_vlans = ','.join(chunk)
            self.cmd(['conf t', 'no vlan {0}'.format(part_of_vlans)])

    def configure_for_osp7(self):
        from lab.logger import lab_logger

        return  # TODO  Nikolay is to revisited here
        ports_n9k = []
        ports_fi_a = []
        ports_fi_b = []
        ports_tor = []
        peer_ip = None

        cdp_neis = self.cmd(['sh cdp nei det'])
        for nei in cdp_neis[0]['result']['body'][u'TABLE_cdp_neighbor_detail_info'][u'ROW_cdp_neighbor_detail_info']:
            port_id = nei['intf_id']
            if 'TOR' in nei['device_id']:
                ports_tor.append(port_id)
            if 'UCS-FI' in nei['platform_id']:
                if '-A' in nei['device_id']:
                    ports_fi_a.append(port_id)
                if '-B' in nei['device_id']:
                    ports_fi_b.append(port_id)
            if 'N9K' in nei['platform_id']:
                    ports_n9k.append(port_id)
                    peer_n9k_ip = nei['v4mgmtaddr']

        def print_or_raise(title, ports_lst):
            if ports:
                lab_logger.info('{0} connected to {1} on {2}'.format(title, ports_lst, self.ip))
            else:
                raise Exception('No ports connected to {0} on {1} found!'.format(title, self.ip))

        print_or_raise(title='FI-A', ports_lst=ports_fi_a)
        print_or_raise(title='FI-B', ports_lst=ports_fi_b)
        print_or_raise(title='N9K', ports_lst=ports_n9k)
        print_or_raise(title='TOR', ports_lst=ports_tor)

        pcs = self.cmd(['sh port-channel summary'])
        if pcs[0]['result']:
            pc_ids = []
            dict_or_list = pcs[0]['result']['body'][u'TABLE_channel'][u'ROW_channel']
            if isinstance(dict_or_list, dict):
                pc_ids.append(dict_or_list['group'])
            else:
                pc_ids = [x['group'] for x in dict_or_list]
            for pc_id in pc_ids:
                self.cmd(['conf t', 'no int port-channel {0}'.format(pc_id)])

        pc_tor, pc_n9k, pc_fi_a, pc_fi_b = 177, 1, ports_fi_a[0].split('/')[-1], ports_fi_b[0].split('/')[-1]

        config = [(ports_n9k, pc_n9k, '1,' + str(user_vlan)),
                  (ports_fi_a, pc_fi_a, '1,' + str(user_vlan)),
                  (ports_fi_b, pc_fi_b, '1,' + str(user_vlan)),
                  (ports_tor, pc_tor, str(user_vlan))]

        self.cmd(['conf t', 'vlan {0}'.format(user_vlan), 'no shut'])

        for ports, pc_id, vlans in config:
            self.cmd(['conf t', 'int port-channel {0}'.format(pc_id),
                      'switchport', 'switchport mode trunk', 'switchport trunk allowed vlan {0}'.format(vlans),
                      'speed 10000', 'feature lacp'])

        for ports, pc_id, vlans in config:
            self.cmd(['conf t', 'int ' + ','.join(ports), 'switchport', 'switchport mode trunk',
                      'switchport trunk allowed vlan {0}'.format(vlans), 'speed 10000',
                      'channel-group {0} mode active'.format(pc_id)])

        self.cmd(['conf t', 'feature vpc'])
        self.cmd(['conf t', 'vpc domain 1', 'peer-keepalive destination {0}'.format(peer_ip)])
        self.cmd(['conf t', 'int port-channel {0}'.format(pc_n9k), 'vpc peer-link'])

        for pc_id in [pc_fi_a, pc_fi_b, pc_tor]:
            self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'vpc {0}'.format(pc_id)])

        self.cmd(['copy run start'])

        return peer_ip
