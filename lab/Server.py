class Server(object):
    def __init__(self, ip, net='??InServer', username='??InServer', password='ssh_key', hostname='??InServer', role='??InServer', n_in_role=0, ssh_public_key='N/A', ssh_port=22):
        self.ip = ip
        self.net = net
        self.ip_mac = 'UnknownInServer'
        self.role = role
        self.n_in_role = n_in_role
        self.hostname = hostname
        self.username = username
        self.password = password
        self.ssh_public_key = ssh_public_key
        self.ssh_port = ssh_port

        self.ipmi = {'ip': 'UnknownInServer', 'username': 'UnknownInServer', 'password': 'UnknownInServer'}
        self.ucsm = {'ip': 'UnknownInServer', 'username': 'UnknownInServer', 'password': 'UnknownInServer', 'service-profile': 'UnknownInServer',
                     'iface_mac': {'UnknownInServer': 'UnknownInServer'}}

        self.nics = []
        self.package_manager = None

    def __repr__(self):
        return 'sshpass -p {0} ssh {1}@{2} {3}'.format(self.password, self.username, self.ip, self.name())

    def name(self):
        return '{0}-{1}'.format(self.role, self.n_in_role)

    def set_ipmi(self, ip, username, password):
        self.ipmi['ip'] = ip
        self.ipmi['username'] = username
        self.ipmi['password'] = password

    def ipmi_creds(self):
        return self.ipmi['ip'], self.ipmi['username'], self.ipmi['password']

    def set_ucsm(self, ip, username, password, service_profile, server_id, is_sriov):
        self.ucsm['ip'] = ip
        self.ucsm['username'] = username
        self.ucsm['password'] = password
        self.ucsm['service-profile'] = service_profile
        self.ucsm['server-id'] = server_id
        self.ucsm['is-sriov'] = is_sriov

    def add_if(self, nic_name, nic_mac, nic_order, nic_vlans):
        self.nics.append([nic_name, nic_mac, nic_order, nic_vlans])

    def ucsm_profile(self):
        return self.ucsm['service-profile']

    def ucsm_is_sriov(self):
        return self.ucsm['is-sriov']

    def ucsm_server_id(self):
        return self.ucsm['server-id']

    def nic_mac(self, nic_name):
        nic = [x for x in self.nics if x[0] == nic_name]
        return nic[0][1]

    def get_package_manager(self):
        if not self.package_manager:
            possible_packages = ['apt-get', 'dnf', 'yum']
            for x in possible_packages:
                if self.run(command='whereis {0}'.format(x)) != x + ':':
                    self.package_manager = x
                    break
            if not self.package_manager:
                raise RuntimeError('do not know which package manager to use: neither of {0} found'.format(possible_packages))
        return self.package_manager

    def construct_settings(self, warn_only):
        from lab import WithConfig

        kwargs = {'host_string': '{user}@{ip}'.format(user=self.username, ip=self.ip),
                  'connection_attempts': 100,
                  'warn_only': warn_only}
        if self.password == 'ssh_key':
            kwargs['key_filename'] = WithConfig.KEY_PRIVATE_PATH
        else:
            kwargs['password'] = self.password
        return kwargs

    def run(self, command, in_directory='.', warn_only=False):
        """Do run with possible sudo on remote server
        :param command:
        :param in_directory:
        :param warn_only:
        :return:
        """
        from fabric.api import run, sudo, settings, cd

        if self.ip == 'localhost' or self.ip == '127.0.0.1':
            return self.run_local(command, in_directory=in_directory, warn_only=warn_only)

        run_or_sudo = run
        if command.startswith('sudo '):
            command = command.replace('sudo ', '')
            run_or_sudo = sudo

        with settings(**self.construct_settings(warn_only=warn_only)):
            with cd(in_directory):
                result = run_or_sudo(command)
                return result

    @staticmethod
    def run_local(command, in_directory='.', warn_only=False):
        from fabric.api import local, settings, lcd

        if in_directory != '.':
            local('mkdir -p {0}'.format(in_directory))
        with settings(warn_only=warn_only):
            with lcd(in_directory):
                return local(command=command, capture=True)

    def put(self, string_to_put, file_name, in_directory='.'):
        """Put given string as file to remote server
        :param string_to_put:
        :param file_name:
        :param in_directory:
        :return:
        """
        from fabric.api import put, settings, cd, lcd, local
        import os
        from StringIO import StringIO

        use_sudo = True if in_directory.startswith('/etc') else False

        if in_directory != '.':
            self.run(command='{0} mkdir -p {1}'.format('sudo' if use_sudo else '', in_directory))

        if self.ip == 'localhost' or self.ip == '127.0.0.1':
            with lcd(in_directory):
                local('echo "{0}" > {1}'.format(string_to_put, file_name))
                return os.path.abspath(os.path.join(in_directory, file_name))
        else:
            with settings(**self.construct_settings(warn_only=False)):
                with cd(in_directory):
                    return put(local_path=StringIO(string_to_put), remote_path=file_name, use_sudo=use_sudo)

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
            self.run(command='{0} mkdir -p {1}'.format('sudo' if use_sudo else '', in_directory))

        if self.ip == 'localhost' or self.ip == '127.0.0.1':
            with lcd(in_directory):
                local('echo "{0}" > {1}'.format(string_to_put, file_name))
                return os.path.abspath(os.path.join(in_directory, file_name))
        else:
            with settings(**self.construct_settings(warn_only=False)):
                with cd(in_directory):
                    return put(local_path=StringIO(string_to_put), remote_path=file_name, use_sudo=use_sudo)

    def get(self, remote_path, in_directory='.', local_path=None):
        """Get remote file as string or local file if local_path is specified
        :param remote_path:
        :param in_directory:
        :param local_path:
        :return:
        """
        from fabric.api import get, settings, cd
        from StringIO import StringIO

        if not local_path:
            local_path = StringIO()

        use_sudo = True if remote_path.startswith('/') else False
        with settings(**self.construct_settings(warn_only=False)):
            with cd(in_directory):
                get(remote_path=remote_path, local_path=local_path,  use_sudo=use_sudo)

        return local_path.getvalue() if isinstance(local_path, StringIO) else local_path

    def get_file_from_dir(self, file_name, in_directory='.', local_path=None):
        """Get remote file as string or local file if local_path is specified
        :param file_name:
        :param in_directory:
        :param local_path:
        :return:
        """
        from fabric.api import sudo, settings, cd

        if '/' in file_name:
            raise SyntaxError('file_name can not contain /, use in_directory instead')

        with settings(**self.construct_settings(warn_only=False)):
            with cd(in_directory):
                body = sudo('cat {0}'.format(file_name))

        if local_path:
            with open(local_path, 'w') as f:
                f.write(body)
            return local_path
        else:
            return body

    def wget_file(self, url, to_directory, checksum):
        import os

        loc = url.split('/')[-1]
        self.run(command='test -e  {loc} || wget -nv {url} -O {loc}'.format(loc=loc, url=url), in_directory=to_directory)
        calc_checksum = self.run(command='sha256sum {loc}'.format(loc=loc), in_directory=to_directory)
        if calc_checksum.split()[0] != checksum:
            self.run(command='rm {0}'.format(loc), in_directory=to_directory)
            raise RuntimeError('I deleted image {0} since it is broken (checksum is not matched). Re-run the script'.format(loc))
        return os.path.abspath(os.path.join(to_directory, loc))

    def check_or_install_packages(self, package_names):
        pm = self.get_package_manager()

        for package_name in package_names.split():
            if self.run(command='whereis {0}'.format(package_name)) == package_name + ':':
                self.run(command='sudo {0} install -y {1}'.format(pm, package_name))

    def clone_repo(self, repo_url, local_repo_dir=None):
        import urlparse

        local_repo_dir = local_repo_dir or urlparse.urlparse(repo_url).path.split('/')[-1].strip('.git')

        self.check_or_install_packages(package_names='git')
        self.run(command='test -d {0} || git clone -q {1} {0}'.format(local_repo_dir, repo_url))
        self.run(command='git pull -q', in_directory=local_repo_dir)
        return self.run(command='pwd', in_directory=local_repo_dir)

    def create_user(self, new_username):
        from lab import WithConfig

        if not self.run(command='grep {0} /etc/passwd'.format(new_username), warn_only=True):
            encrypted_password = self.run(command='openssl passwd -crypt {0}'.format(self.password))
            self.run(command='sudo adduser -p {0} {1}'.format(encrypted_password.split()[-1], new_username))  # encrypted password may contain Warning
            self.run(command='sudo echo "{0} ALL=(root) NOPASSWD:ALL" | tee -a /etc/sudoers.d/{0}'.format(new_username))
            self.run(command='sudo chmod 0440 /etc/sudoers.d/{0}'.format(new_username))
        self.username = new_username
        with open(WithConfig.KEY_PUBLIC_PATH) as f:
            self.put_string_as_file_in_dir(string_to_put=f.read(), file_name='authorized_keys', in_directory='.ssh')
        self.run(command='sudo chmod 700 .ssh')
        self.run(command='sudo chmod 600 .ssh/authorized_keys')
