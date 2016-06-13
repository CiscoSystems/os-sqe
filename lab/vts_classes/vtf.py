from lab.server import Server


class Vtf(Server):
    COMMANDS = ['show vxlan tunnel', 'show version', 'show ip fib', 'show l2fib verbose', 'show br', 'show br 5000 detail' 'trace add dpdk-input 100']  # supported- expect files are pre-created

    def __init__(self, node_id, role, lab, hostname):
        super(Vtf, self).__init__(node_id=node_id, role=role, lab=lab, hostname=hostname)
        self._commands = {cmd: '{name}-{cmd}-expect'.format(cmd='-'.join(cmd.split()), name=self.get_id()) for cmd in self.COMMANDS}
        self._proxy_to_run = None

    def __repr__(self):
        return u'{0} proxy {1}'.format(self.get_id(), self._proxy_to_run)

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
        ip, username, password = self.get_ssh()
        return self._proxy_to_run.run(command='sshpass -p {p} ssh {u}@{ip} '.format(p=password, u=username, ip=ip) + command)

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
        ip, username, password = self.get_ssh()
        for cmd, file_name in self._commands.iteritems():
            tmpl = '''
log_user 0
spawn sshpass -p {p} ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no {u}@{ip} telnet 0 5002
expect "vpp#"
send "{cmd}\r"
log_user 1
send "quit\r"
expect eof
'''.format(p=password, u=username, ip=ip, cmd=cmd)
            self._proxy_to_run.put_string_as_file_in_dir(string_to_put=tmpl, file_name=file_name)
        self.cmd('show version')

    def get_compute_node(self):
        for w in self.get_all_wires():
            n = w.get_peer_node(self)
            if 'compute' in n.role():
                return n

    def get_config_and_net_part_bodies(self):
        from lab import with_config

        config_tmpl = with_config.read_config_from_file(config_path='vtf_vm_config.txt', directory='vts', is_as_string=True)
        net_part_tmpl = with_config.read_config_from_file(config_path='vtf-net-part-of-libvirt-domain.template', directory='vts', is_as_string=True)
        compute = self.get_all_wires()[0].get_peer_node(self)

        compute_hostname = compute.hostname()
        nic_vts_net = filter(lambda x: x.is_vts(), self.get_nics().values())[0]
        loc_ip, loc_netmask = nic_vts_net.get_ip_and_mask()
        loc_gw = nic_vts_net.get_net()[1]
        vlan = nic_vts_net.get_net().get_vlan()
        dns_ip = self.lab().get_dns()[0]
        ntp_ip = self.lab().get_ntp()[0]
        _, ssh_username, ssh_password = self.get_ssh()
        config_body = config_tmpl.format(loc_ip=loc_ip, loc_netmask=loc_netmask, loc_gw=loc_gw, dns_ip=dns_ip, ntp_ip=ntp_ip, vtc_loc_ip=' TODO: ',  # TODO
                                         username=ssh_username, password=ssh_password, compute_hostname=compute_hostname)
        net_part = net_part_tmpl.format(vlan=vlan)
        return config_body, net_part