from lab.nodes.lab_server import LabServer


class Vtf(LabServer):
    ROLE = 'vtf'

    def __init__(self, node_id, role, lab):
        super(Vtf, self).__init__(node_id=node_id, role=role, lab=lab)
        self._expect_commands = {}
        self._proxy_to_run = None
        self._vtf_container_name = None
        self._vtf_container_name = 'neutron_vtf_4388'  # TODO: parametrize build number

    def __repr__(self):
        return u'{id} ({ip}) proxy {p}'.format(id=self.get_id(), ip=self._oob_ip, p=self._proxy_to_run)

    # noinspection PyMethodOverriding
    def cmd(self, cmd):
        from lab.vts_classes.vtc import Vtc

        if not self._proxy_to_run:
            self.lab().get_nodes_by_class(Vtc)[-1].r_vtc_get_vtfs()

        if cmd not in self._expect_commands:
            self.create_expect_command_file(cmd=cmd)
        ans = self._proxy_to_run.exe(command='expect {0}'.format(self._expect_commands[cmd]))
        return ans

    def create_expect_command_file(self, cmd):
        ip, username, password = self.get_oob()
        file_name = 'expect-{}-{}'.format(self.get_id(), cmd.replace(' ', '-'))
        tmpl = '''
log_user 0
spawn sshpass -p {p} ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -t {u}@{ip} docker exec -it {c} telnet 0 5002
expect "vpp#"
send "{cmd}\r"
log_user 1
send "quit\r"
expect eof
'''.format(p=password, u=username, ip=ip, cmd=cmd, c=self._vtf_container_name)
        self._proxy_to_run.r_put_string_as_file_in_dir(string_to_put=tmpl, file_name=file_name)
        self._expect_commands[cmd] = file_name

    def vtf_show_vxlan_tunnel(self):
        return self.cmd('show vxlan tunnel')

    def vtf_show_version(self):
        return self.cmd('show version')

    def vtf_show_ip_fib(self):
        return self.cmd('show ip fib')

    def vtf_show_l2fib(self):
        return self.cmd('show l2fib verbose')

    def vtf_show_connections_xrvr_vtf(self):
        return self.exe('netstat -ant |grep 21345')

    def vtf_trace(self):
        return self.exe('trace add dpdk-input 100')

    def get_compute_node(self):
        for w in self.get_all_wires():
            n = w.get_peer_node(self)
            if 'compute' in n.role():
                return n

    def vtf_show_int(self):
        return self.cmd('show int')
