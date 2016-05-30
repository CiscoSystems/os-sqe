from lab.server import Server


class Vtf(Server):
    def cmd(self, cmd):
        a = '''
log_user 0
spawn sshpass -p {p} ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no {u}@{ip} telnet 0 5002
expect "vpp#"
send "{cmd}\r"
log_user 1
send "quit\r"
expect eof
'''.format(p=self._ipmi_password, u=self._ipmi_username, ip=self._ipmi_ip, cmd=cmd)
        file_name = self.put_string_as_file_in_dir(string_to_put=a, file_name='expect_to_run')
        wire_to_vtc = self.get_all_wires()[0]
        vtc_server = wire_to_vtc.get_peer_node(self)
        ans = vtc_server.run(command='expect {0}'.format(file_name))
        return ans.split('\n')[-2]

    def run(self, command, in_directory='.', warn_only=False):
        return super(Vtf, self).run(command='sshpass -p {p} ssh {u}@{ip} '.format(p=self._ipmi_password, u=self._ipmi_username, ip=self._ipmi_ip) + command)


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

    def get_vtfs(self):
        from lab.wire import Wire

        self.check_or_install_packages('sshpass')
        ans = self._rest_api(resource='/api/running/cisco-vts')
        for ip_addess in ans['cisco-vts:cisco-vts']['vtfs']['vtf']:
            _, ip = ip_addess.items()[0]
            username, password = 'cisco', 'cisco123'
            vtf = Vtf(name='vtf1', role='vtf', ip=self._ip, username=self._username, password=self._password, lab=self.lab(), hostname='????')
            vtf.set_ipmi(ip=ip, username=username, password=password)
            vtf.actuate_hostname()
            Wire(node_n=self, port_n='A', node_s=vtf, port_s='B', mac_s='', nic_s='', vlans=[])
            vtf.cmd(cmd='show version')

