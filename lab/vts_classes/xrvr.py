from lab.server import Server

# use telnet 0 5087 from xrnc to see the bootstrap process just after spinning up XRNC VM
# configuration is kept in sudo cat /etc/vpe/vsocsr/dl_server.ini on cisco@xrnc
# error loging in /var/log/sr/dl_registration_errors.log


class Xrvr(Server):
    def __init__(self, node_id, role, lab, hostname):
        super(Xrvr, self).__init__(node_id=node_id, role=role, lab=lab, hostname=hostname)
        self._expect_commands = {}
        self._proxy_to_run = None

    def __repr__(self):
        _, ssh_u, ssh_p = self.get_ssh()
        _, oob_u, oob_p = self.get_oob()
        ip = self.get_nic('mx').get_ip_and_mask()[0]
        return u'{l} {n} | sshpass -p {p} ssh {u1}/{u2}@{ip} for XRVR/DL'.format(l=self.lab(), n=self.get_id(), ip=ip, p=ssh_p, u1=oob_u, u2=ssh_u)

    # noinspection PyMethodOverriding
    def cmd(self, cmd, is_xrvr):  # XRVR uses redirection: ssh_username goes to DL while oob_username goes to XRVR, ip and password are the same for both
        from lab.vts_classes.vtc import VtsHost

        if not self._proxy_to_run:
            self._proxy_to_run = self.lab().get_nodes_by_class(VtsHost)[-1]

        if is_xrvr:
            if cmd not in self._expect_commands:
                self.create_expect_command_file(cmd=cmd)
            ans = self._proxy_to_run.run(command='expect {0}'.format(self._expect_commands[cmd]))
        else:
            _, username, password = self.get_ssh()
            ip = self.get_nic('mx').get_ip_and_mask()[0]
            ans = self._proxy_to_run.run(command='sshpass -p {p} ssh -o StrictHostKeyChecking=no -t {u}@{ip} {cmd}'.format(p=password, u=username, ip=ip, cmd=cmd))
        return ans

    def create_expect_command_file(self, cmd):
        _, username, password = self.get_oob()
        ip = self.get_nic('mx').get_ip_and_mask()[0]
        file_name = 'expect-{}-{}'.format(self.get_id(), cmd.replace(' ', '-'))
        tmpl = '''
log_user 0
spawn sshpass -p {p} ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no {u}@{ip}
expect "CPU0:XRVR"
send "terminal length 0 ; {cmd}\n"
log_user 1
expect "CPU0:XRVR"
'''.format(p=password, u=username, ip=ip, cmd=cmd)
        self._proxy_to_run.put_string_as_file_in_dir(string_to_put=tmpl, file_name=file_name)
        self._expect_commands[cmd] = file_name

    @staticmethod
    def _get(raw, key):
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
        return self.cmd('show running-config', is_xrvr=True)

    def show_host(self, evi, mac):
        # mac should look like 0010.1000.2243
        mac = mac.replace(':', '').lower()
        mac = '.'.join([mac[0:4], mac[4:8], mac[8:16]])

        cmd = 'show running-config evpn evi {0} network-control host mac {1}'.format(evi, mac)
        raw = self.cmd(cmd, is_xrvr=True)
        if 'No such configuration item' not in raw:
            return {
                'ipv4_address': self._get(raw, 'ipv4 address'),
                'switch': self._get(raw, 'switch'),
                'mac': self._get(raw, 'host mac'),
                'evi': self._get(raw, 'evi')
            }
        return None

    def show_evpn(self):
        return self.cmd('show running-config evpn', is_xrvr=True)

    def show_connections_xrvr_vtf(self):
        return self.run('netstat -ant |grep 21345')

    def get_config_and_net_part_bodies(self):
        from lab import with_config

        cfg_tmpl = with_config.read_config_from_file(config_path='xrnc-vm-config.txt', directory='vts', is_as_string=True)
        net_part_tmpl = with_config.read_config_from_file(config_path='xrnc-net-part-of-libvirt-domain.template', directory='vts', is_as_string=True)

        dns_ip, ntp_ip = self.lab().get_dns()[0], self.lab().get_ntp()[0]
        xrvr_name = '{id}-{lab}'.format(lab=self.lab(), id=self.get_id())
        xrnc_name = xrvr_name.replace('xrvr', 'xrnc')

        _, vtc_username, vtc_password = self.lab().get_node_by_id('vtc1').get_oob()
        _, ssh_username, ssh_password = self.get_ssh()
        _, oob_username, oob_password = self.get_oob()

        mx_nic = self.get_nic('mx')  # XRNC sits on mx and t nets
        te_nic = self.get_nic('t')

        vtc_mx_vip = mx_nic.get_net()[150]

        dl_mx_ip, mx_net_mask = mx_nic.get_ip_and_mask()
        mx_gw, mx_net_len = mx_nic.get_net()[1], mx_nic.get_net().prefixlen
        xrvr_mx_ip = mx_nic.get_net()[200 + int(self.get_id()[-1])]

        dl_te_ip, te_net_mask = te_nic.get_ip_and_mask()
        te_vlan = te_nic.get_net().get_vlan()
        te_net_len = te_nic.get_net().prefixlen
        xrvr_te_ip = te_nic.get_net()[200 + int(self.get_id()[-1])]

        # XRVR is a VM sitting in a VM which runs on vts-host. outer VM called DL inner VM called XRVR , so 2 IPs on ssh and vts networks needed
        cfg_body = cfg_tmpl.format(dl_mx_ip=dl_mx_ip, xrvr_mx_ip=xrvr_mx_ip, mx_net_mask=mx_net_mask, mx_net_len=mx_net_len, mx_gw=mx_gw,
                                   dl_te_ip=dl_te_ip, xrvr_te_ip=xrvr_te_ip, te_net_mask=te_net_mask, te_net_len=te_net_len, dns_ip=dns_ip, ntp_ip=ntp_ip,
                                   vtc_mx_ip=vtc_mx_vip,
                                   xrnc_username=ssh_username, xrvr_username=oob_username, xrvr_password=oob_password, vtc_username=vtc_username, vtc_password=vtc_password,
                                   xrnc_name=xrnc_name, xrvr_name=xrvr_name)
        with with_config.open_artifact(xrnc_name, 'w') as f:
            f.write(cfg_body)
        net_part = net_part_tmpl.format(mx_nic_name=mx_nic.get_name(), t_nic_name=te_nic.get_name(), t_vlan=te_vlan)

        return cfg_body, net_part

    def get_logs(self):
        body = ''
        for cmd in ['grep -i error /var/log/sr/*']:
            ans = self.cmd(cmd=cmd, is_xrvr=False)
            body += self._format_single_cmd_output(cmd=cmd, ans=ans)
        return body

    def dl_start_server(self):
        own_ip = self.get_nic('t').get_ip_and_mask()[0]
        ips = [x.get_nic('t').get_ip_and_mask()[0] for x in self.lab().get_nodes_by_class(Xrvr)]
        opposite_ip = next(iter(set(ips) - {own_ip}))
        self.cmd('sudo ip l s dev br-underlay mtu 1400', is_xrvr=False)  # https://cisco.jiveon.com/docs/DOC-1455175 step 12 about MTU
        self.cmd('sudo /opt/cisco/package/sr/bin/setupXRNC_HA.sh {}'.format(opposite_ip), is_xrvr=False)  # https://cisco.jiveon.com/docs/DOC-1455175 Step 11

        return True

    def restart_dl_server(self):
        return self.cmd('sudo crm resource restart dl_server', is_xrvr=False)

    def xrnc_get_interfaces_config(self):
        import re
        interfaces_text = self.cmd('cat /etc/network/interfaces', is_xrvr=False)

        config = {}
        interface_name = ''
        for line in interfaces_text.split('\r\n'):
            sr = re.search('iface (?P<name>.*?) inet', line)
            if sr:
                interface_name = sr.group('name')
                config[interface_name] = ''
            if interface_name:
                config[interface_name] += line + '\r\n'
        return config
