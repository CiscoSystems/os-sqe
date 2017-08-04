from lab.with_config import WithConfig


class Server(WithConfig):
    N_CONNECTION_ATTEMPTS = 200

    def __init__(self, ip, username, password):
        self._tmp_dir_exists = False
        self._package_manager = None
        self.username, self.password, self.hostname = username, password, None
        self.ip = ip if type(ip) is not list else ip[0]
        self.via_proxy = ''

    def get_package_manager(self):
        if not self._package_manager:
            possible_packages = ['apt-get', 'dnf', 'yum']
            for x in possible_packages:
                if self.exe(command='whereis {0}'.format(x)) != x + ':':
                    self._package_manager = x
                    break
            if not self._package_manager:
                raise RuntimeError('do not know which package manager to use: neither of {0} found'.format(possible_packages))
        return self._package_manager

    def construct_settings(self, is_warn_only, connection_attempts):
        kwargs = {'host_string': '{user}@{ip}'.format(user=self.username, ip=self.ip),
                  'disable_known_hosts': True,
                  'connection_attempts': connection_attempts,
                  'warn_only': is_warn_only}
        if self.password is None:
            kwargs['key'] = self.PRIVATE_KEY
        else:
            kwargs['password'] = self.password
        return kwargs

    @staticmethod
    def _exe_local(command, in_directory='.', warn_only=False):
        from fabric.api import local, settings, lcd

        if in_directory != '.':
            local('mkdir -p {0}'.format(in_directory))
        with settings(warn_only=warn_only):
            with lcd(in_directory):
                return local(command=command, capture=True)

    def form_cmd_string(self, cmd, in_dir):
        if 'sudo' in cmd and 'sudo -p "" -S ' not in cmd:
            cmd = cmd.replace('sudo ', 'echo {} | sudo -p "" -S '.format(self.password))

        if self.via_proxy:
            cmd = self.via_proxy + ' "' + cmd + '"'
        return cmd + ' # in ' + in_dir + ' pass: ' + str(self.password)

    def exe(self, command, in_directory='.', is_warn_only=False, connection_attempts=N_CONNECTION_ATTEMPTS):
        from fabric.api import run, settings, cd
        from fabric.exceptions import NetworkError

        cmd = self.form_cmd_string(cmd=command, in_dir=in_directory)
        if str(self.ip) in ['localhost', '127.0.0.1']:
            return self._exe_local(cmd, in_directory=in_directory, warn_only=is_warn_only)

        # with settings(**self.construct_settings(is_warn_only=is_warn_only, connection_attempts=connection_attempts)):
        with settings(**self.construct_settings(is_warn_only=True, connection_attempts=connection_attempts)):
            with cd(in_directory):
                try:
                    res = run(cmd)
                except NetworkError:
                    if is_warn_only:
                        return ''
                    else:
                        raise
        if not is_warn_only:
            if res and res.return_code != 0:
                raise Exception(res.stderr)
        return res

    def file_append(self, file_path, data, in_directory='.', is_warn_only=False, connection_attempts=N_CONNECTION_ATTEMPTS):
        from fabric.api import settings, cd
        from fabric.contrib import files
        from fabric.exceptions import NetworkError

        with settings(**self.construct_settings(is_warn_only=is_warn_only, connection_attempts=connection_attempts)):
            with cd(in_directory):
                try:
                    return files.append(file_path, data)
                except NetworkError:
                    if is_warn_only:
                        return ''
                    else:
                        raise

    def reboot(self, wait=300):
        """Reboot this server
        :param wait: wait for the server to come up
        """
        from fabric.api import reboot, settings
        with settings(**self.construct_settings(is_warn_only=True, connection_attempts=self.N_CONNECTION_ATTEMPTS)):
            reboot(wait=wait)

    def put(self, local_path, remote_path, is_sudo):
        """Faced the normal fabric put to provide server details from the class
        :param local_path:
        :param remote_path:
        :param is_sudo:
        :return:
        """
        from fabric.api import put, settings

        with settings(**self.construct_settings(is_warn_only=False, connection_attempts=self.N_CONNECTION_ATTEMPTS)):
            return put(local_path=local_path, remote_path=remote_path, use_sudo=is_sudo)

    def check_or_install_packages(self, package_names):
        pm = self.get_package_manager()

        for package_name in package_names.split():
            if self.exe(command='whereis {0}'.format(package_name)) == package_name + ':':
                self.exe(command='sudo {0} install -y {1}'.format(pm, package_names))

    def r_ping(self, port=22):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        try:
            s.connect((str(self.ip), port))
            res = True
        except (socket.timeout, socket.error):
            res = False
        finally:
            s.close()
        return res

    def actuate_hostname(self, refresh=True):
        if not hasattr(self, '_hostname') or refresh:
            self.hostname = self.exe('hostname').stdout.strip()
        return self.hostname

    def r_list_ip_info(self, connection_attempts=100):
        ans_a = self.exe('ip -o a', connection_attempts=connection_attempts, is_warn_only=True)
        if not ans_a:
            return {}
        ans_l = self.exe('ip -o l', connection_attempts=connection_attempts, is_warn_only=True)
        name_ipv4_ipv6 = {}
        result = {}

        for line in ans_a.split('\n'):
            _, nic_name, other = line.split(' ', 2)
            name_ipv4_ipv6.setdefault(nic_name, {'ipv4': [], 'ipv6': []})
            ip4_or_6 = 'ipv6' if 'inet6' in other else 'ipv4'
            ip = other.split()[1].strip()
            name_ipv4_ipv6[nic_name][ip4_or_6].append(ip)
            result.setdefault(ip, [])
            result[ip].append(nic_name)

        for line in ans_l.split('\n'):
            number, nic_name, other = line.split(':', 2)
            nic_name = nic_name.strip()
            if nic_name == 'lo':
                continue
            status, mac_part = other.split('link/ether')
            mac = mac_part.split(' brd ')[0].strip()
            ipv4 = name_ipv4_ipv6.get(nic_name, {'ipv4': []})['ipv4']
            ipv6 = name_ipv4_ipv6.get(nic_name, {'ipv6': []})['ipv6']
            result[nic_name] = {'mac': mac, 'ipv4': ipv4, 'ipv6': ipv6}
            result.setdefault(mac, [])
            result[mac].append(nic_name)
        return result
