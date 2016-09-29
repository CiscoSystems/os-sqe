class Server(object):
    N_CONNECTION_ATTEMPTS = 200
    USE_SSH_KEY = 'ssh_key'

    def __repr__(self):
        return u'sshpass -p {} ssh {}@{}'.format(self._password, self._username, self._ip)

    def __init__(self, ip, username, password):
        self._tmp_dir_exists = False
        self._package_manager = None
        self._mac_server_part = None
        self._ip, self._username, self._password, self._hostname = ip, username, password, None

    def set_ssh_ip(self, ip):
        self._ip = ip

    def get_ssh_ip(self):
        return self._ip

    def get_ssh(self):
        return self._ip, self._username, self._password

    def get_hostname(self):
        return self._hostname

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
        from lab import with_config

        kwargs = {'host_string': '{user}@{ip}'.format(user=self._username, ip=self._ip),
                  'connection_attempts': connection_attempts,
                  'warn_only': is_warn_only}
        if self._password == 'ssh_key':
            kwargs['key_filename'] = with_config.KEY_PRIVATE_PATH
        else:
            kwargs['password'] = self._password
        return kwargs

    @staticmethod
    def _exe_local(command, in_directory='.', warn_only=False):
        from fabric.api import local, settings, lcd

        if in_directory != '.':
            local('mkdir -p {0}'.format(in_directory))
        with settings(warn_only=warn_only):
            with lcd(in_directory):
                return local(command=command, capture=True)

    def exe(self, command, in_directory='.', is_warn_only=False, connection_attempts=N_CONNECTION_ATTEMPTS):
        from fabric.api import run, sudo, settings, cd
        from fabric.exceptions import NetworkError

        if str(self._ip) in ['localhost', '127.0.0.1']:
            return self._exe_local(command, in_directory=in_directory, warn_only=is_warn_only)

        run_or_sudo = run
        if command.startswith('sudo '):
            command = command.replace('sudo ', '')
            run_or_sudo = sudo

        with settings(**self.construct_settings(is_warn_only=is_warn_only, connection_attempts=connection_attempts)):
            with cd(in_directory):
                try:
                    return run_or_sudo(command)
                except NetworkError:
                    if is_warn_only:
                        return ''
                    else:
                        raise

    def as_proxy(self, host, command, is_warn_only=False, connection_attempts=N_CONNECTION_ATTEMPTS):
        return self.exe("ssh -o StrictHostKeyChecking=no {} '{}'".format(host, command), is_warn_only=is_warn_only, connection_attempts=connection_attempts)

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

    def put_string_as_file_in_dir(self, string_to_put, file_name, in_directory='.'):
        """Put given string as file to remote server
        :param string_to_put:
        :param file_name:
        :param in_directory:
        :return:
        """
        from fabric.api import put, settings, cd, lcd, local
        import os
        from StringIO import StringIO

        if '/' in file_name:
            raise SyntaxError('file_name can not contain /, use in_directory instead')

        use_sudo = True if in_directory.startswith('/') else False

        if in_directory != '.':
            self.exe(command='{0} mkdir -p {1}'.format('sudo' if use_sudo else '', in_directory))

        if str(self._ip) in ['localhost', '127.0.0.1']:
            with lcd(in_directory):
                local('echo "{0}" > {1}'.format(string_to_put, file_name))
                return os.path.abspath(os.path.join(in_directory, file_name))
        else:
            with settings(**self.construct_settings(is_warn_only=False, connection_attempts=self.N_CONNECTION_ATTEMPTS)):
                with cd(in_directory):
                    return put(local_path=StringIO(string_to_put), remote_path=file_name, use_sudo=use_sudo)[0]

    def r_get_file_from_dir(self, file_name, in_directory='.', local_path=None):
        """Get remote file as string or local file if local_path is specified
        :param file_name:
        :param in_directory:
        :param local_path:
        :return:
        """
        from fabric.api import sudo, settings, cd, get

        if '/' in file_name:
            raise SyntaxError('file_name can not contain /, use in_directory instead')

        with settings(**self.construct_settings(is_warn_only=False, connection_attempts=self.N_CONNECTION_ATTEMPTS)):
            with cd(in_directory):
                if local_path:
                    local_path = get(remote_path=file_name, local_path=local_path)
                    return local_path
                else:
                    body = sudo('cat {0}'.format(file_name))
                    return body

    def wget_file(self, url, to_directory='.', checksum=None, method='sha512sum'):
        loc = url.split('/')[-1]
        if to_directory != '.':
            self.exe('mkdir -p {0}'.format(to_directory))
        self.exe(command='test -e  {loc} || curl -s -R {url} -o {loc}'.format(loc=loc, url=url), in_directory=to_directory)

        calc_checksum = self.exe(command='{meth} {loc}'.format(meth=method, loc=loc), in_directory=to_directory)
        if checksum:
            if calc_checksum.split()[0] != checksum:
                self.exe(command='rm -f {0}'.format(loc), in_directory=to_directory)
                raise RuntimeError('I deleted image {} taken from {} since it is broken (checksum is not matched). Re-run the script'.format(loc, url))
        return self.exe(command='readlink -f {0}'.format(loc), in_directory=to_directory)

    def check_or_install_packages(self, package_names):
        pm = self.get_package_manager()

        for package_name in package_names.split():
            if self.exe(command='whereis {0}'.format(package_name)) == package_name + ':':
                self.exe(command='sudo {0} install -y {1}'.format(pm, package_names))

    def clone_repo(self, repo_url, local_repo_dir=None, tags=None, patch=None):
        local_repo_dir = local_repo_dir or repo_url.split('/')[-1].strip('.git')

        self.check_or_install_packages(package_names='git')
        self.exe(command='test -d {0} || git clone -q {1} {0}'.format(local_repo_dir, repo_url))
        self.exe(command='git pull -q', in_directory=local_repo_dir)
        if patch:
            self.exe(command='git fetch {0} && git checkout FETCH_HEAD'.format(patch))
        elif tags:
            self.exe(command='git checkout tags/{0}'.format(tags), in_directory=local_repo_dir)
        return self.exe(command='pwd', in_directory=local_repo_dir)

    def r_create_user(self, new_username):
        tmp_password = 'cisco123'
        if not self.exe(command='grep {0} /etc/passwd'.format(new_username), is_warn_only=True):
            encrypted_password = self.exe(command='openssl passwd -crypt {0}'.format(tmp_password))
            self.exe(command='sudo adduser -p {0} {1}'.format(encrypted_password.split()[-1], new_username))  # encrypted password may contain Warning
            self.exe(command='sudo echo "{0} ALL=(root) NOPASSWD:ALL" | tee -a /etc/sudoers.d/{0}'.format(new_username))
            self.exe(command='sudo chmod 0440 /etc/sudoers.d/{0}'.format(new_username))
        self._username, self._password = new_username, tmp_password
        self.r_deploy_ssh_key()
        self._password = 'ssh_key'

    def r_deploy_ssh_key(self):
        from lab import with_config
        with open(with_config.KEY_PUBLIC_PATH) as f:
            self.put_string_as_file_in_dir(string_to_put=f.read(), file_name='authorized_keys', in_directory='.ssh')
        self.exe(command='chmod 700 .ssh')
        self.exe(command='chmod 600 .ssh/authorized_keys')

    def ping(self, port=22):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        try:
            s.connect((str(self._ip), port))
            res = True
        except (socket.timeout, socket.error):
            res = False
        finally:
            s.close()
        return res

    def actuate_hostname(self, refresh=True):
        if not hasattr(self, '_hostname') or refresh:
            self._hostname = self.exe('hostname').stdout.strip()
        return self._hostname

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
