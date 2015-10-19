class Server(object):
    def __init__(self, ip, username, password, hostname='Unknown', ssh_public_key='N/A', ssh_port=22):
        import os
        from lab.WithConfig import CONFIG_DIR

        self.private_key_path = os.path.join(CONFIG_DIR, 'keys', 'private')

        self.ip = ip
        self.ip_mac = 'UnknownInServer'
        self.hostname = hostname
        self.username = username
        self.password = password
        self.ssh_public_key = ssh_public_key
        self.ssh_port = ssh_port

        self.ipmi = {'ip': 'UnknownInServer', 'username': 'UnknownInServer', 'password': 'UnknownInServer'}
        self.ucsm = {'ip': 'UnknownInServer', 'username': 'UnknownInServer', 'password': 'UnknownInServer', 'service-profile': 'UnknownInServer',
                     'iface_mac': {'UnknownInServer': 'UnknownInServer'}}

        self.package_manager = None

    def __repr__(self):
        return 'sshpass -p {0} ssh {1}@{2}'.format(self.password, self.username, self.ip)

    def set_ipmi(self, ip, username, password):
        self.ipmi['ip'] = ip
        self.ipmi['username'] = username
        self.ipmi['password'] = password

    def set_ucsm(self, ip, username, password, service_profile, iface_mac):
        self.ucsm['ip'] = ip
        self.ucsm['username'] = username
        self.ucsm['password'] = password
        self.ucsm['service-profile'] = service_profile
        self.ucsm['iface_mac'] = iface_mac

    def get_mac(self, iface_name):
        return self.ucsm['iface_mac'].get(iface_name, 'UnknownInServer')

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
        kwargs = {'host_string': '{user}@{ip}'.format(user=self.username, ip=self.ip),
                  'connection_attempts': 50,
                  'warn_only': warn_only}
        if self.password == 'ssh_key':
            kwargs['key_filename'] = self.private_key_path
        else:
            kwargs['password'] = self.password
        return kwargs

    def run(self, command, in_directory='.', warn_only=False):
        """Do run with possible sudo on remote server"""
        from fabric.api import run, sudo, settings, cd

        run_or_sudo = run
        if command.startswith('sudo '):
            command = command.replace('sudo ', '')
            run_or_sudo = sudo

        with settings(**self.construct_settings(warn_only=warn_only)):
            with cd(in_directory):
                result = run_or_sudo(command)
                return result

    def put(self, string_to_put, remote_path, in_directory='.'):
        """Put given string as file to remote server"""
        from fabric.api import put, settings, cd
        from StringIO import StringIO

        use_sudo = True if remote_path.startswith('/') else False
        with settings(**self.construct_settings(warn_only=False)):
            self.run(command='sudo mkdir -p {0}'.format(in_directory))
            with cd(in_directory):
                return put(local_path=StringIO(string_to_put), remote_path=remote_path, use_sudo=use_sudo)

    def get(self, remote_path, in_directory='.', local_path=None):
        """Get remote file as string or local file if local_path is specified"""
        from fabric.api import get, settings, cd
        from StringIO import StringIO

        if not local_path:
            local_path = StringIO()

        use_sudo = True if remote_path.startswith('/') else False
        with settings(**self.construct_settings(warn_only=False)):
            with cd(in_directory):
                get(remote_path=remote_path, local_path=local_path,  use_sudo=use_sudo)

        return local_path.getvalue() if isinstance(local_path, StringIO) else local_path

    def wget_file(self, url, to_directory, checksum):
        loc = url.split('/')[-1]
        self.run(command='mkdir -p {0}'.format(to_directory))
        self.run(command='test -e  {loc} || wget -nv {url} -O {loc}'.format(loc=loc, url=url), in_directory=to_directory)
        calc_checksum = self.run(command='sha256sum {loc}'.format(loc=loc), in_directory=to_directory)
        if calc_checksum.split()[0] != checksum:
            self.run(command='rm {0}'.format(loc), in_directory=to_directory)
            raise RuntimeError('I deleted image {0} since it is broken (checksum is not matched). Re-run the script'.format(loc))
        return loc

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
        if not self.run(command='grep {0} /etc/passwd'.format(new_username), warn_only=True):
            encrypted_password = self.run(command='openssl passwd -crypt {0}'.format(self.password))
            self.run(command='sudo adduser -p {0} {1}'.format(encrypted_password, new_username))
            self.run(command='sudo echo "{0} ALL=(root) NOPASSWD:ALL" | tee -a /etc/sudoers.d/{0}'.format(new_username))
            self.run(command='sudo chmod 0440 /etc/sudoers.d/{0}'.format(new_username))
        self.username = new_username
