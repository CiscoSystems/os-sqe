from lab.lab_node import LabNode


class Nic(object):
    def __repr__(self):
        return u'{0} {1}'.format(self._name, self._mac)

    def __init__(self, name, mac, node):
        self._node = node  # nic belongs to the node
        self._name = name
        self._mac = mac

    def get_mac(self):
        return self._mac

    def get_name(self):
        return self._name


class Server(LabNode):

    _temp_dir = None

    @property
    def temp_dir(self):
        if not self._temp_dir:
            import os
            import random

            chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_'
            self._temp_dir = os.path.join('/tmp', 'server-tmp-' + ''.join(random.sample(chars, 10)))

        if not self._tmp_dir_exists:
            from fabric.api import settings

            # if self.run('test -d {0}'.format(self._temp_dir), warn_only=True).return_code:
            #     self._tmp_dir_exists = self.run('mkdir -p {0}'.format(self._temp_dir)).return_code == 0
        return self._temp_dir if self._tmp_dir_exists else None

    def __init__(self, name, ip, lab, username='??InServer', password='ssh_key', hostname='??InServer'):
        self._tmp_dir_exists = False
        self._package_manager = None
        self._ipmi_ip, self._ipmp_username, self._ipmi_password = None, None, None
        self._mac_server_part = None
        self._nics = list()  # list of NICs
        self._is_nics_formed = False

        super(Server, self).__init__(name=name, ip=ip, username=username, password=password, lab=lab, hostname=hostname)

    def __repr__(self):
        return '{n} | sshpass -p {p} ssh {u}@{ip} | ipmitool -I lanplus -H {ip2} -U {u2} -P {p2}'.format(p=self._password, u=self._username, ip=self._ip, n=self.name(), ip2=self._ipmi_ip, u2=self._ipmp_username, p2=self._ipmi_password)

    def set_ipmi(self, ip, username, password):
        self._ipmi_ip, self._ipmp_username, self._ipmi_password = ip, username, password

    def get_ipmi(self):
        return self._ipmi_ip, self._ipmp_username, self._ipmi_password

    def add_nics(self, nics):
        """:param: nics is a list ['eth0', 'eth1', 'user', ''pxe'] """
        self._nics.extend(nics)

    def _form_nics(self):
        if not self._is_nics_formed:
            if not self._mac_server_part:
                raise RuntimeError('{0} is not ready to form nics- character part of mac is not set!')
            l = []
            for nic_name, mac_net_part in self._nics:
                mac = '{lab_id:02}:00:{srv_part}:00:{net_part}'.format(lab_id=self.lab().get_id(), srv_part=self._mac_server_part, net_part=mac_net_part)
                self.lab().make_sure_that_object_is_unique(type_of_object='MAC', obj=mac, node_name=self.name())
                l.append(Nic(name=nic_name, mac=mac, node=self))
            self._nics = l
            self._is_nics_formed = True

    def get_nic(self, nic):
        return filter(lambda x: x.get_name() == nic, self._nics)

    def get_nics(self):
        return self._nics

    def get_package_manager(self):
        if not self._package_manager:
            possible_packages = ['apt-get', 'dnf', 'yum']
            for x in possible_packages:
                if self.run(command='whereis {0}'.format(x)) != x + ':':
                    self._package_manager = x
                    break
            if not self._package_manager:
                raise RuntimeError('do not know which package manager to use: neither of {0} found'.format(possible_packages))
        return self._package_manager

    def construct_settings(self, warn_only):
        from lab import with_config

        kwargs = {'host_string': '{user}@{ip}'.format(user=self._username, ip=self._ip),
                  'connection_attempts': 10,
                  'warn_only': warn_only}
        if self._password == 'ssh_key':
            kwargs['key_filename'] = with_config.KEY_PRIVATE_PATH
        else:
            kwargs['password'] = self._password
        return kwargs

    def cmd(self, command, in_directory='.', warn_only=False):
        return NotImplementedError

    def run(self, command, in_directory='.', warn_only=False):
        """Do run with possible sudo on remote server
        :param command:
        :param in_directory:
        :param warn_only:
        :return:
        """
        from fabric.api import run, sudo, settings, cd

        if self._ip == 'localhost' or self._ip == '127.0.0.1':
            return self.run_local(command, in_directory=in_directory, warn_only=warn_only)

        run_or_sudo = run
        if command.startswith('sudo '):
            command = command.replace('sudo ', '')
            run_or_sudo = sudo

        with settings(**self.construct_settings(warn_only=warn_only)):
            with cd(in_directory):
                result = run_or_sudo(command)
                return result

    def reboot(self, wait=300):
        """Reboot this server
        :param wait: wait for the server to come up
        """
        from fabric.api import reboot, settings
        with settings(**self.construct_settings(warn_only=True)):
            reboot(wait=wait)

    @staticmethod
    def run_local(command, in_directory='.', warn_only=False):
        from fabric.api import local, settings, lcd

        if in_directory != '.':
            local('mkdir -p {0}'.format(in_directory))
        with settings(warn_only=warn_only):
            with lcd(in_directory):
                return local(command=command, capture=True)

    def put(self, local_path, remote_path, is_sudo):
        """Faced the normal fabric put to provide server details from the class
        :param local_path:
        :param remote_path:
        :param is_sudo:
        :return:
        """
        from fabric.api import put, settings

        with settings(**self.construct_settings(warn_only=False)):
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
            self.run(command='{0} mkdir -p {1}'.format('sudo' if use_sudo else '', in_directory))

        if self._ip == 'localhost' or self._ip == '127.0.0.1':
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

    def check_rally(self):
        rally_installed = False
        self.check_or_install_packages(package_names='git')
        if not self.run(command='cd rally', warn_only=True):
            rally_installed = True
        return rally_installed

    def clone_repo(self, repo_url, local_repo_dir=None, tags=None):
        import urlparse

        local_repo_dir = local_repo_dir or urlparse.urlparse(repo_url).path.split('/')[-1].strip('.git')

        self.check_or_install_packages(package_names='git')
        self.run(command='test -d {0} || git clone -q {1} {0}'.format(local_repo_dir, repo_url))
        self.run(command='git pull -q', in_directory=local_repo_dir)
        if tags:
            self.run(command='git checkout tags/{0}'.format(tags), in_directory=local_repo_dir)
        return self.run(command='pwd', in_directory=local_repo_dir)

    def create_user(self, new_username):
        from lab import with_config

        password = 'cisco123'
        if not self.run(command='grep {0} /etc/passwd'.format(new_username), warn_only=True):
            encrypted_password = self.run(command='openssl passwd -crypt {0}'.format(password))
            self.run(command='sudo adduser -p {0} {1}'.format(encrypted_password.split()[-1], new_username))  # encrypted password may contain Warning
            self.run(command='sudo echo "{0} ALL=(root) NOPASSWD:ALL" | tee -a /etc/sudoers.d/{0}'.format(new_username))
            self.run(command='sudo chmod 0440 /etc/sudoers.d/{0}'.format(new_username))
        self._username = new_username
        self._password = 'cisco123'
        with open(with_config.KEY_PUBLIC_PATH) as f:
            self.put_string_as_file_in_dir(string_to_put=f.read(), file_name='authorized_keys', in_directory='.ssh')
        self.run(command='sudo chmod 700 .ssh')
        self.run(command='sudo chmod 600 .ssh/authorized_keys')
        self._password = 'ssh_key'

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
    
    def actuate_hostname(self):
        self._hostname = self.run('hostname').stdout.strip()
        return self._hostname
