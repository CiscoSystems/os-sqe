from lab.server import Server


class Xrvr(Server):
    COMMANDS = ['show running-config', 'show running-config evpn']  # supported- expect files are pre-created

    def __init__(self, node_id, role, lab, hostname):
        super(Xrvr, self).__init__(node_id=node_id, role=role, lab=lab, hostname=hostname)
        self._commands = {cmd: '{name}-{cmd}-expect'.format(cmd='-'.join(cmd.split()), name=self.get_id()) for cmd in self.COMMANDS}
        self._proxy_to_run = None

        self._init_commands()

    def _add_command(self, cmd):
        file_name = '{name}-{cmd}-expect'.format(cmd='-'.join(cmd.split()), name=self.get_id())
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
        for cmd, file_name in self._commands.items():
            self.actuate_command(cmd, file_name)

    def actuate_command(self, cmd, file_name):
        ip, username, password = self.get_oob()
        tmpl = '''
log_user 0
spawn sshpass -p {p} ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no {u}@{ip}
expect "CPU0:XRVR"
send "terminal length 0 ; {cmd}\n"
log_user 1
expect "CPU0:XRVR"
'''.format(p=password, u=username, ip=ip, cmd=cmd)
        self._proxy_to_run.put_string_as_file_in_dir(string_to_put=tmpl, file_name=file_name)

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
