from lab.nodes.virtual_server import VirtualServer


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

