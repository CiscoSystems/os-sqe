from lab.server import Server


class Vtf(Server):
    COMMANDS = ['show vxlan tunnel', 'show version', 'show ip fib', 'show l2fib verbose', 'show br', 'show br 5000 detail' 'trace add dpdk-input 100']  # supported- expect files are pre-created

    def __init__(self, name, role, ip, lab, username, password, hostname):
        super(Vtf, self).__init__(name, role, ip, lab, username, password, hostname)
        self._commands = {cmd: '{name}-{cmd}-expect'.format(cmd='-'.join(cmd.split()), name=self._name) for cmd in self.COMMANDS}
        self._proxy_to_run = None

    def __repr__(self):
        return u'{0} proxy {1}'.format(self._name, self._proxy_to_run)

    def set_proxy(self, proxy):
        self._proxy_to_run = proxy

    def cmd(self, cmd):  # this one needs to run via telnet on vtf host
        if not self._proxy_to_run:
            raise RuntimeError('{0} needs to have proxy server (usually VTC)'.format(self))
        ans = self._proxy_to_run.run(command='expect {0}'.format(self._commands[cmd]))
        return ans.split('\n')[3:-1]

    def run(self, command, in_directory='.', warn_only=False):  # this one imply runs the command on vtf host (without telnet)
        if not self._proxy_to_run:
            raise RuntimeError('{0} needs to have proxy server (usually VTC)'.format(self))
        return self._proxy_to_run.run(command='sshpass -p {p} ssh {u}@{ip} '.format(p=self._password, u=self._username, ip=self._ip) + command)

    def show_vxlan_tunnel(self):
        return self.cmd('show vxlan tunnel')

    def show_version(self):
        return self.cmd('show version')

    def show_ip_fib(self):
        return self.cmd('show ip fib')

    def show_l2fib(self):
        return self.cmd('show l2fib verbose')

    def show_connections_xrvr_vtf(self):
        return self.run('netstat -ant |grep 21345')

    def trace(self):
        return self.run('trace add dpdk-input 100')

    def actuate(self):
        for cmd, file_name in self._commands.iteritems():
            tmpl = '''
log_user 0
spawn sshpass -p {p} ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no {u}@{ip} telnet 0 5002
expect "vpp#"
send "{cmd}\r"
log_user 1
send "quit\r"
expect eof
'''.format(p=self._password, u=self._username, ip=self._ip, cmd=cmd)
            self._proxy_to_run.put_string_as_file_in_dir(string_to_put=tmpl, file_name=file_name)
        self.cmd('show version')

    def get_compute_node(self):
        for w in self.get_all_wires():
            n = w.get_peer_node(self)
            if 'compute' in n.role():
                return n

class Xrvr(Server):
    COMMANDS = ['show running-config', 'show running-config evpn']  # supported- expect files are pre-created

    def __init__(self, name, role, ip, lab, username, password, hostname):
        super(Xrvr, self).__init__(name, role, ip, lab, username, password, hostname)
        self._commands = {}
        self._proxy_to_run = None

        self._init_commands()

    def _add_command(self, cmd):
        file_name = '{name}-{cmd}-expect'.format(cmd='-'.join(cmd.split()), name=self._name)
        self._commands[cmd] = file_name
        return file_name

    def _init_commands(self):
        self._commands = {}
        for cmd in self.COMMANDS:
            self._add_command(cmd)

    def set_proxy(self, proxy):
        self._proxy_to_run = proxy

    def cmd(self, cmd):  # XRVR uses redirection: username goes to DL while ipmi_username goes to XRVR, ip is the same for both
        if not self._proxy_to_run:
            raise RuntimeError('{0} needs to have proxy server (usually VTC)'.format(self))
        if cmd not in self._commands:
            file_name = self._add_command(cmd)
            self.actuate_command(cmd, file_name)
        ans = self._proxy_to_run.run(command='expect {0}'.format(self._commands[cmd]))
        return ans

    def actuate(self):
        for cmd, file_name in self._commands.iteritems():
            self.actuate_command(cmd, file_name)

    def actuate_command(self, cmd, file_name):
        tmpl = '''
log_user 0
spawn sshpass -p {p} ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no {u}@{ip}
expect "CPU0:XRVR"
send "terminal length 0 ; {cmd}\n"
log_user 1
expect "CPU0:XRVR"
'''.format(p=self._ipmi_password, u=self._ipmi_username, ip=self._ip, cmd=cmd)
        self._proxy_to_run.put_string_as_file_in_dir(string_to_put=tmpl, file_name=file_name)

    def _get(self, raw, key):
        """
        Return values of a key element found in raw text.
        :param raw: looks like :
            evpn
             evi 10000
              network-controller
               host mac fa16.3e5b.9162
                ipv4 address 10.23.23.2
                switch 11.12.13.9
                gateway 10.23.23.1 255.255.255.0
                vlan 1002
        :param key: A key string. Ex: vlan, gateway
        :return: Value of a key parameter
        """
        import re
        try:
            # First 2 lines are the called command
            # The last line is a prompt
            for line in raw.split('\r\n')[2:-1]:
                if line.startswith('#'):
                    continue
                m = re.search('\s*(?<={0} )(.*?)\r'.format(key), line)
                if m:
                    return m.group(1)
        except AttributeError:
            return None

    def show_running_config(self):
        return self.cmd('show running-config')

    def show_host(self, evi, mac):
        # mac should look like 0010.1000.2243
        mac = mac.replace(':', '').lower()
        mac = '.'.join([mac[0:4], mac[4:8], mac[8:16]])

        cmd = 'show running-config evpn evi {0} network-control host mac {1}'.format(evi, mac)
        raw = self.cmd(cmd)
        if 'No such configuration item' not in raw:
            return {
                'ipv4_address': self._get(raw, 'ipv4 address'),
                'switch': self._get(raw, 'switch'),
                'mac': self._get(raw, 'host mac'),
                'evi': self._get(raw, 'evi')
            }
        return None

    def show_evpn(self):
        return self.cmd('show running-config evpn')

    def restart_dl_server(self):
        return self.run('sudo crm resource restart dl_server')

    def show_connections_xrvr_vtf(self):
        return self.run('netstat -ant |grep 21345')


class Vts(Server):
    def _rest_api(self, resource, params=None):
        import requests
        import json
        from lab.logger import lab_logger

        from requests.packages import urllib3

        urllib3.disable_warnings()  # Suppressing warning due to self-signed certificate

        resource = resource.strip('/')
        url = 'https://{ip}:{port}/{resource}'.format(ip=self._ipmi_ip, port=8888, resource=resource)
        auth = (self._ipmi_username, self._ipmi_password)
        headers = {'Accept': 'application/vnd.yang.data+json'}

        # noinspection PyBroadException
        try:
            res = requests.get(url, auth=auth, headers=headers, params=params, timeout=100, verify=False)
            return json.loads(res.text)
        except:
            lab_logger.exception('Url={url} auth={auth},vtc headers={headers}, param={params}'.format(url=url, auth=auth, headers=headers, params=params))

    def cmd(self, cmd, **kwargs):
        return self._rest_api(resource=cmd)

    def get_vni_pool(self):
        ans = self._rest_api(resource='/api/running/resource-pools/vni-pool/vnipool')
        return ans

    def get_vtf(self, compute_hostname):
        for vtf in self.lab().get_nodes(Vtf):
            n = vtf.get_compute_node()
            if n.actuate_hostname(refresh=False) == compute_hostname:
                return vtf

    def check_vtfs(self):
        self.check_or_install_packages('sshpass')
        ans = self._rest_api(resource='/api/running/cisco-vts')
        vtf_ips_from_vtc = [x['ip'] for x in ans['cisco-vts:cisco-vts']['vtfs']['vtf']]
        vtf_nodes = self.lab().get_nodes(Vtf)
        for vtf in vtf_nodes:
            ip, _, _, _ = vtf.get_ssh()
            if str(ip) not in vtf_ips_from_vtc:
                raise RuntimeError('{0} is not detected by {1}'.format(vtf, self))
            vtf.actuate()
        return vtf_nodes

    def check_xrvr(self):
        xrvr_nodes = self.lab().get_nodes(Xrvr)
        items = self.json_api_get_network_inventory()['items']
        xrvr_ips_from_vtc = [x['ip_address'] for x in items if 'ASR9K' == x['devicePlaform'] and 'xrvr' in x['id'].lower()]
        for xrvr in xrvr_nodes:
            ip, _, _, _ = xrvr.get_ssh()
            if str(ip) not in xrvr_ips_from_vtc:
                raise RuntimeError('{0} is not detected by {1}'.format(xrvr, self))
            xrvr.actuate()
        return xrvr_nodes

    def json_api_url(self, resource):
        import os
        url = 'https://{ip}:{port}/VTS'.format(ip=self._ipmi_ip, port=8443)
        return os.path.join(url, resource)

    def json_api_session(self):
        import requests

        s = requests.Session()
        auth = s.post(self.json_api_url('j_spring_security_check'), data={'j_username': self._ipmi_username, 'j_password': self._ipmi_password, 'Submit': 'Login'}, verify=False)
        if 'Invalid username or passphrase' in auth.text:
            raise Exception('Invalid username or passphrase')

        return s

    def json_api_get(self, resource):
        s = None
        r = {'items': []}
        try:
            s = self.json_api_session()
            response = s.get(self.json_api_url(resource))
            if response.status_code == 200:
                r = response.json()
        except Exception as e:
            raise e
        finally:
            s.close()
        return r

    def json_api_get_network_inventory(self):
        return self.json_api_get('rs/ncs/query/networkInventory')

    def restart_dl_server(self):
        return map(lambda xrvr: xrvr.restart_dl_server(), self.lab().get_nodes(Xrvr))

    def show_evpn(self):
        return map(lambda xrvr: xrvr.show_evpn(), self.lab().get_nodes(Xrvr))

    def show_connections_xrvr_vtf(self):
        return map(lambda vtf: vtf.show_connections_xrvr_vtf(), self.lab().get_nodes(Vtf)) + map(lambda xrvr: xrvr.show_connections_xrvr_vtf(), self.lab().get_nodes(Xrvr))

    def show_vxlan_tunnel(self):
        return map(lambda vtf: vtf.show_vxlan_tunnel(), self.lab().get_nodes(Vtf))

    def show_logs(self, what='error'):
        self.run('grep -i {0} /var/log/ncs/*'.format(what), warn_only=True)

    def show_uuid_servers(self):
        pass  # ncs_cli -u admin show configuration cisco-vts uuid-servers

    def disrupt(self, start_or_stop):
        pass  # TODO: implement actual disruptor when devs ready

    def actuate(self):
        self.check_xrvr()
        self.check_vtfs()

    def get_overlay_networks(self, name='admin'):
        return self.json_api_get('rs/ncs/query/topologiesNetworkAll?limit=2147483647&name=' + name)

    def get_overlay_network(self, network_id):
        networks = self.get_overlay_networks()
        for network in networks['items']:
            if network_id == network['id']:
                return network

    def get_overlay_network_subnets(self, network_id, topology_id='admin', name='admin'):
        resource = 'rs/ncs/query/networkSubnetInfoPopover?' \
                   'limit=2147483647&name={n}&network-id={net_id}&topologyId={t}'.format(net_id=network_id,
                                                                                         t=topology_id,
                                                                                         n=name)
        return self.json_api_get(resource)

    def get_overlay_network_ports(self, network_id):
        resource = 'rs/vtsService/tenantTopology/admin/admin/ports?network-Id={0}'.format(network_id)
        return self.json_api_get(resource)

    def get_overlay_network_port(self, network_id, port_id):
        ports = self.get_overlay_network_ports(network_id)
        for port in ports['items']:
            if port_id == port['id']:
                return port

    def get_overlay_routers(self, name='admin'):
        return self.json_api_get('rs/ncs/query/topologiesRouterAll?limit=2147483647&name=' + name)

    def get_verlay_virtual_machines(self, name='admin'):
        return self.json_api_get('rs/ncs/query/topologiesRouterAll?limit=2147483647&name=' + name)

    def get_overlay_devices(self):
        return self.json_api_get('rs/ncs/query/devices?limit=2147483647')

    def get_overlay_vms(self, name='admin'):
        return self.json_api_get('rs/ncs/query/tenantPortsAll?limit=2147483647&name=' + name)

    def get_overlay_device_vlan_vni_mapping(self, device_name):
        resource = 'rs/ncs/operational/vlan-vni-mapping/{0}'.format(device_name)
        return self.json_api_get(resource)

    def verify_network(self, os_network):
        overlay_network = self.get_overlay_network(os_network['id'])
        net_flag = False
        if overlay_network:
            net_flag = True
            net_flag &= overlay_network['name'] == os_network['name']
            net_flag &= overlay_network['status'] == os_network['status'].lower()
            net_flag &= overlay_network['admin-state-up'] == os_network['admin_state_up'].lower()
            net_flag &= overlay_network['provider-network-type'] == os_network['provider:network_type']
            net_flag &= overlay_network['provider-physical-network'] == os_network['provider:physical_network']
            net_flag &= overlay_network['provider-segmentation-id'] == os_network['provider:segmentation_id']
            net_flag &= overlay_network['provider-segmentation-id'] == os_network['provider:segmentation_id']
        return net_flag

    def verify_subnet(self, os_network_id, os_subnet):
        overlay_subnet = self.get_overlay_network_subnets(os_network_id)['items']
        subnet_synced = len(overlay_subnet) > 0
        if subnet_synced:
            overlay_subnet = overlay_subnet[0]
            subnet_synced &= overlay_subnet['cidr'] == os_subnet['cidr']
            subnet_synced &= overlay_subnet['enable-dhcp'] == os_subnet['enable_dhcp'].lower()
            subnet_synced &= overlay_subnet['gateway-ip'] == os_subnet['gateway_ip']
            subnet_synced &= overlay_subnet['id'] == os_subnet['id']
            subnet_synced &= overlay_subnet['ip-version'] == os_subnet['ip_version']
            subnet_synced &= overlay_subnet['name'] == os_subnet['name']
            subnet_synced &= overlay_subnet['network-id'] == os_subnet['network_id']
        return subnet_synced

    def verify_ports(self, os_network_id, os_ports):
        overlay_ports = self.get_overlay_network_ports(network_id=os_network_id)['items']
        ports_synced = len(overlay_ports) == len(os_ports)
        if ports_synced:
            for port in os_ports:
                try:
                    overlay_port = next(p for p in overlay_ports if p['id'] == port['id'])
                    ports_synced &= overlay_port['mac'] == port['mac_address']
                except StopIteration:
                    ports_synced = False
                    break
        return ports_synced

    def verify_instances(self, os_instances):
        vms = self.get_overlay_vms()['items']
        instances_synced = len(vms) == len(os_instances)
        return instances_synced