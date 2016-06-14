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
        for cmd, file_name in self._commands.iteritems():
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

        cfg_tmpl = with_config.read_config_from_file(config_path='xrnc_vm_config.txt', directory='vts', is_as_string=True)
        net_part_tmpl = with_config.read_config_from_file(config_path='xrnc-net-part-of-libvirt-domain.template', directory='vts', is_as_string=True)

        dns_ip, ntp_ip = self.lab().get_dns()[0], self.lab().get_ntp()[0]
        lab_name = str(self.lab())

        _, username, password = self.get_ssh()

        nic_ssh_net = filter(lambda x: x.is_ssh(), self.get_nics().values())[0]  # Vtc sits on out-of-tor network marked is_ssh
        dl_ssh_ip, ssh_netmask = nic_ssh_net.get_ip_and_mask()
        ssh_gw = nic_ssh_net.get_net()[1]
        ssh_prefixlen = nic_ssh_net.get_net().prefixlen

        nic_vts_net = filter(lambda x: x.is_vts(), self.get_nics().values())[0]  # also sits on local network marked is_vts
        dl_loc_ip, loc_netmask = nic_vts_net.get_ip_and_mask()
        vlan = nic_vts_net.get_net().get_vlan()
        loc_prefixlen = nic_ssh_net.get_net().prefixlen

        # TODO: parametrize xrvr_ip and vtc_vip
        xrvr_loc_ip = nic_vts_net.get_net()[170 + int(self.get_id()[-1])]
        xrvr_ssh_ip = nic_vts_net.get_net()[42 + int(self.get_id()[-1])]
        vtc_vip = '10.23.221.150'

        # XRVR is a VM sitting in a VM which runs on vts-host. outer VM called DL inner VM called XRVR , so 2 IPs on ssh and vts networks needed
        cfg_body = cfg_tmpl.format(ssh_ip_dl=dl_ssh_ip, ssh_ip_xrvr=xrvr_ssh_ip, ssh_netmask=ssh_netmask, ssh_prefixlen=ssh_prefixlen, ssh_gw=ssh_gw,
                                   loc_ip_dl=dl_loc_ip, loc_ip_xrvr=xrvr_loc_ip, loc_netmask=loc_netmask, loc_prefixlen=loc_prefixlen, dns_ip=dns_ip, ntp_ip=ntp_ip,
                                   vtc_ssh_ip=vtc_vip, username=username, password=password, lab_name=lab_name)
        net_part = net_part_tmpl.format(ssh_nic_name=nic_ssh_net.get_name(), vts_nic_name=nic_vts_net.get_name(), vlan=vlan)

        return cfg_body, net_part