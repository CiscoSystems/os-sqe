from lab.server import Server


class Vtf(Server):
    def __init__(self, name, role, ip, lab, username, password, hostname):
        super(Vtf, self).__init__(name, role, ip, lab, username, password, hostname)
        self._commands = {}
        self._proxy_to_run = None

    def cmd(self, cmd):  # this one needs to run via telnet on vtf host
        ans = self._proxy_to_run.run(command='expect {0}'.format(self._commands[cmd]))
        return ans.split('\n')[-2]

    def run(self, command, in_directory='.', warn_only=False):  # this one imply runs the command on vtf host (without telnet)
        return self._proxy_to_run.run(command='sshpass -p {p} ssh {u}@{ip} '.format(p=self._password, u=self._username, ip=self._ip) + command)

    def show_vxlan_tunnel(self):
        return self.cmd('show vxlan tunnel')

    def show_version(self):
        return self.cmd('show version')

    def actuate(self, proxy):
        self._proxy_to_run = proxy

        for cmd in ['show vxlan tunnel', 'show version']:
            tmpl = '''
log_user 0
spawn sshpass -p {p} ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no {u}@{ip} telnet 0 5002
expect "vpp#"
send "{cmd}\r"
log_user 1
send "quit\r"
expect eof
'''.format(p=self._password, u=self._username, ip=self._ip, cmd=cmd)
            file_name = 'expect-to-run-' + '-'.join(cmd.split()) + '-' + self._name
            file_name = self._proxy_to_run.put_string_as_file_in_dir(string_to_put=tmpl, file_name=file_name)
            self._commands[cmd] = file_name
        self.cmd('show version')


class Xrvr(Server):
    def __init__(self, name, role, ip, lab, username, password, hostname):
        super(Xrvr, self).__init__(name, role, ip, lab, username, password, hostname)
        self._commands = {}
        self._proxy_to_run = None

    def cmd(self, cmd):  # XRVR uses redirection: username goes to DL while ipmi_username goes to XRVR, ip is the same for both
        ans = self._proxy_to_run.run(command='expect {0}'.format(self._commands[cmd]))
        return ans

    def actuate(self, proxy):
        self._proxy_to_run = proxy  # we use proxy just to keep all expect files in a single place

        for cmd in ['show running-config']:
            tmpl = '''
log_user 0
spawn sshpass -p {p} ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no {u}@{ip}
expect "CPU0:XRVR"
send "terminal length 0 ; show running-config\n"
log_user 1
expect eof
'''.format(p=self._ipmi_password, u=self._ipmi_username, ip=self._ip, cmd=cmd)
            file_name = 'expect-to-run-' + '-'.join(cmd.split()) + '-' + self._name
            file_name = self._proxy_to_run.put_string_as_file_in_dir(string_to_put=tmpl, file_name=file_name)
            self._commands[cmd] = file_name

    def show_running_config(self):
        return self.cmd('show running-config')


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

    def check_vtfs(self):
        self.check_or_install_packages('sshpass')
        ans = self._rest_api(resource='/api/running/cisco-vts')
        vtf_ips_from_vtc = [x['ip'] for x in ans['cisco-vts:cisco-vts']['vtfs']['vtf']]
        vtf_nodes = self.lab().get_nodes(Vtf)
        for vtf in vtf_nodes:
            ip, _, _, _ = vtf.get_ssh()
            if str(ip) not in vtf_ips_from_vtc:
                raise RuntimeError('{0} is not detected by {1}'.format(vtf, self))
            vtf.actuate(proxy=self)
        return vtf_nodes

    def check_xrvr(self):
        xrvr_nodes = self.lab().get_nodes(Xrvr)
        items = self.json_api_get_network_inventory()['items']
        xrvr_ips_from_vtc = [x['ip_address'] for x in items if 'ASR9K' == x['devicePlaform'] and 'xrvr' in x['id'].lower()]
        for xrvr in xrvr_nodes:
            ip, _, _, _ = xrvr.get_ssh()
            if str(ip) not in xrvr_ips_from_vtc:
                raise RuntimeError('{0} is not detected by {1}'.format(xrvr, self))
            xrvr.actuate(proxy=self)
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
        r = None
        try:
            s = self.json_api_session()
            r = s.get(self.json_api_url(resource))
        except Exception as e:
            raise e
        finally:
            s.close()
        return r.json()

    def json_api_get_network_inventory(self):
        return self.json_api_get('rs/ncs/query/networkInventory')
