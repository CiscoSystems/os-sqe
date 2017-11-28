from lab.nodes.virtual_server import VirtualServer, LibVirtServer


class Vtsr(VirtualServer):
    def __init__(self, **kwargs):
        super(Vtsr, self).__init__(**kwargs)
        self._expect_commands = {}

    # noinspection PyMethodOverriding
    def cmd(self, cmd, is_xrvr, is_warn_only=False):  # XRVR uses redirection: ssh_username goes to DL while oob_username goes to XRVR, ip and password are the same for both
        ip = self.get_ip_mx()

        if is_xrvr:
            _, username, password = self.get_oob()
            if cmd not in self._expect_commands:
                self.create_expect_command_file(cmd=cmd, ip=ip, username=username, password=password, is_xrvr=True)
            ans = self._proxy.exe(command='expect {0}'.format(self._expect_commands[cmd]), is_warn_only=is_warn_only)
        else:
            ans = self.exe(command=cmd, is_warn_only=is_warn_only)
        return ans

    def disrupt(self, method_to_disrupt, downtime):
        import time

        vts_host = self.get_hardware_server()
        if method_to_disrupt == 'vm-shutdown':
            # self.get_id()[-1] if id is "xrnc1" => 1, "xrnc2" => 2
            vts_host.exe(command='virsh suspend xrnc{}'.format(self.get_node_id()[-1]))
            time.sleep(downtime)
            vts_host.exe(command='virsh resume xrnc{}'.format(self.get_node_id()[-1]))
        elif method_to_disrupt == 'corosync-stop':
            self.cmd('sudo service corosync stop', is_xrvr=False)
            time.sleep(downtime)
            self.cmd('sudo service corosync start', is_xrvr=False)
        elif method_to_disrupt == 'ncs-stop':
            self.cmd('sudo service ncs stop', is_xrvr=False)
            time.sleep(downtime)
            self.cmd('sudo service ncs start', is_xrvr=False)
        elif method_to_disrupt == 'vm-reboot':
            self.exe('set -m; sudo bash -c "ip link set dev eth0 down && ip link set dev eth1 down && sleep {0} && shutdown -r now" 2>/dev/null >/dev/null &'.format(downtime), is_warn_only=True)
            time.sleep(downtime)
        elif method_to_disrupt == 'isolate-from-mx':
            # self.get_id()[-1] if id is "xrnc1" => 1, "xrnc2" => 2
            ans = vts_host.exe('ip l | grep mgmt | grep xrnc{}'.format(self.get_node_id()[-1]))
            if_name = ans.split()[1][:-1]
            vts_host.exe('ip l s dev {} down'.format(if_name))
            time.sleep(downtime)
            vts_host.exe('ip l s dev {} up'.format(if_name))
        elif method_to_disrupt == 'isolate-from-t':
            # self.get_id()[-1] if id is "xrnc1" => 1, "xrnc2" => 2
            ans = vts_host.exe('ip l | grep tenant | xrnc{}'.format(self.get_node_id()[-1]))
            if_name = ans.split()[1][:-1]
            vts_host.exe('ip l s dev {} down'.format(if_name))
            time.sleep(downtime)
            vts_host.exe('ip l s dev {} up'.format(if_name))


class VtsrIndividual(LibVirtServer):
    pass
