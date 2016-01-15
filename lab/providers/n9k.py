from fabric.api import task


class Nexus(object):
    def __init__(self, n9k_ip, n9k_username, n9k_password):
        self.n9k_ip = n9k_ip
        self.n9k_username = n9k_username
        self.n9k_password = n9k_password

    def _allow_feature_nxapi(self):
        from fabric.api import settings, run

        with settings(host_string='{user}@{ip}'.format(user=self.n9k_username, ip=self.n9k_ip), password=self.n9k_password):
            if 'disabled'in run('sh feature | i nxapi', shell=False):
                run('conf t ; feature nxapi', shell=False)

    def _rest_api(self, commands):
        import requests
        import json

        body = [{"jsonrpc": "2.0", "method": "cli", "params": {"cmd": command, "version": 1}, "id": 1} for command in commands]
        try:
            return requests.post('http://{0}/ins'.format(self.n9k_ip), auth=(self.n9k_username, self.n9k_password),
                                 headers={'content-type': 'application/json-rpc'}, data=json.dumps(body)).json()
        except requests.exceptions.ConnectionError:
            self._allow_feature_nxapi()
            return self._rest_api(commands=commands)

    def cmd(self, commands):
        if isinstance(commands, basestring):  # it might be provided as a string where commands are separated by ','
            commands = commands.strip('[]')
            commands = commands.split(',')

        results = self._rest_api(commands=commands)
        if len(commands) == 1:
            results = [results]
        for i, x in enumerate(results, start=0):
            if 'error' in x:
                raise NameError('{cmd} : {msg}'.format(msg=x['error']['data']['msg'].strip('%\n'), cmd=commands[i]))
        return results

    def show_port_channel_summary(self):
        res = self.cmd(['show port-channel summary'])
        return [x['port-channel'] for x in res[0]['result']['body']['TABLE_channel']['ROW_channel']]

    def show_interface_switchport(self, name):
        res = self.cmd(['show interface {0} switchport'.format(name)])
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
        vlans = [x['vlanshowbr-vlanname'] for x in res[0]['result']['body']['TABLE_vlanbrief']['ROW_vlanbrief']]
        return vlans

    def show_users(self):
        res = self.cmd(['show users'])[0]['result']
        if res:
            return res['body']
        else:
            return res

    def no_vlans(self, pattern):
        vlans = filter(lambda x: pattern in x, self.show_vlan())
        vlan_ids = [x.strip('pattern') for x in vlans]
        self.cmd(['conf t', 'no vlan {0}'.format(','.join(vlan_ids))])

    def execute_on_given_n9k(self, user_vlan):
        from lab.logger import lab_logger

        ports_n9k = []
        ports_fi_a = []
        ports_fi_b = []
        ports_tor = []
        peer_n9k_ip = None

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
                lab_logger.info('{0} connected to {1} on {2}'.format(title, ports_lst, self.n9k_ip))
            else:
                raise Exception('No ports connected to {0} on {1} found!'.format(title, self.n9k_ip))

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
        self.cmd(['conf t', 'vpc domain 1', 'peer-keepalive destination {0}'.format(peer_n9k_ip)])
        self.cmd(['conf t', 'int port-channel {0}'.format(pc_n9k), 'vpc peer-link'])

        for pc_id in [pc_fi_a, pc_fi_b, pc_tor]:
            self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'vpc {0}'.format(pc_id)])

        self.cmd(['copy run start'])

        return peer_n9k_ip


@task
def configure_for_osp7(yaml_path):
    """configures n9k to run on top of UCSM
    :param yaml_path: lab configuration file
    """
    from lab.laboratory import Laboratory

    l = Laboratory(yaml_path)
    n9k_ip1, n9k_ip2, n9k_username, n9k_password = l.n9k_creds()
    user_vlan = l.external_vlan()
    n1 = Nexus(n9k_ip1, n9k_username, n9k_password)
    n2 = Nexus(n9k_ip2, n9k_username, n9k_password)

    assert n9k_ip2, n1.execute_on_given_n9k(user_vlan=user_vlan)
    assert n9k_ip1, n2.execute_on_given_n9k(user_vlan=user_vlan)
