from lab.lab_node import LabNode


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

    def __init__(self, node_id, role, lab, hostname):
        self._tmp_dir_exists = False
        self._package_manager = None
        self._mac_server_part = None

        super(Server, self).__init__(node_id=node_id, role=role, lab=lab, hostname=hostname)

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

    def construct_settings(self, warn_only, connection_attempts=100):
        import validators
        from lab import with_config

        ssh_ip, ssh_username, ssh_password = self.get_ssh()
        ssh_ip = ssh_ip if validators.ipv4(ssh_ip) else self.get_oob()[0]

        kwargs = {'host_string': '{user}@{ip}'.format(user=ssh_username, ip=ssh_ip),
                  'connection_attempts': connection_attempts,
                  'warn_only': warn_only}
        if ssh_password == 'ssh_key':
            kwargs['key_filename'] = with_config.KEY_PRIVATE_PATH
        else:
            kwargs['password'] = ssh_password
        return kwargs

    def cmd(self, cmd):
        raise NotImplementedError

    def run(self, command, in_directory='.', warn_only=False, connection_attempts=100):
        from fabric.api import run, sudo, settings, cd
        from fabric.exceptions import NetworkError

        if str(self.get_ssh_ip()) in ['localhost', '127.0.0.1']:
            return self.run_local(command, in_directory=in_directory, warn_only=warn_only)

        run_or_sudo = run
        if command.startswith('sudo '):
            command = command.replace('sudo ', '')
            run_or_sudo = sudo

        with settings(**self.construct_settings(warn_only=warn_only, connection_attempts=connection_attempts)):
            with cd(in_directory):
                try:
                    return run_or_sudo(command)
                except NetworkError as ex:
                    if warn_only:
                        self.log(message=ex.message, level='warning')
                        return ''
                    else:
                        raise

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

        if str(self.get_ssh_ip()) in ['localhost', '127.0.0.1']:
            with lcd(in_directory):
                local('echo "{0}" > {1}'.format(string_to_put, file_name))
                return os.path.abspath(os.path.join(in_directory, file_name))
        else:
            with settings(**self.construct_settings(warn_only=False)):
                with cd(in_directory):
                    return put(local_path=StringIO(string_to_put), remote_path=file_name, use_sudo=use_sudo)[0]

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

    def wget_file(self, url, to_directory='.', checksum=None):
        loc = url.split('/')[-1]
        if to_directory != '.':
            self.run('mkdir -p {0}'.format(to_directory))
        self.run(command='test -e  {loc} || curl {url} -o {loc}'.format(loc=loc, url=url), in_directory=to_directory)
        if checksum == 'in-file':
            checksum = self.run('curl {0}'.format(url + '.sha256sum.txt')).split()[0]

        calc_checksum = self.run(command='sha256sum {loc}'.format(loc=loc), in_directory=to_directory)
        if checksum:
            if calc_checksum.split()[0] != checksum:
                self.run(command='rm {0}'.format(loc), in_directory=to_directory)
                raise RuntimeError('I deleted image {}  taken from {} since it is broken (checksum is not matched). Re-run the script'.format(loc, url + '.sha256sum.txt'))
        else:
            self.log('Checksum was not provided and not found in <url>.sha256sum.txt. Calculated checksum is {}'.format(calc_checksum))
        return self.run(command='readlink -f {0}'.format(loc), in_directory=to_directory)

    def check_or_install_packages(self, package_names):
        pm = self.get_package_manager()

        for package_name in package_names.split():
            if self.run(command='whereis {0}'.format(package_name)) == package_name + ':':
                self.run(command='sudo {0} install -y {1}'.format(pm, package_names))

    def clone_repo(self, repo_url, local_repo_dir=None, tags=None, patch=None):
        import urlparse

        local_repo_dir = local_repo_dir or urlparse.urlparse(repo_url).path.split('/')[-1].strip('.git')

        self.check_or_install_packages(package_names='git')
        self.run(command='test -d {0} || git clone -q {1} {0}'.format(local_repo_dir, repo_url))
        self.run(command='git pull -q', in_directory=local_repo_dir)
        if patch:
            self.run(command='git fetch {0} && git checkout FETCH_HEAD'.format(patch))
        elif tags:
            self.run(command='git checkout tags/{0}'.format(tags), in_directory=local_repo_dir)
        return self.run(command='pwd', in_directory=local_repo_dir)

    def create_user(self, new_username):
        from lab import with_config

        tmp_password = 'cisco123'
        if not self.run(command='grep {0} /etc/passwd'.format(new_username), warn_only=True):
            encrypted_password = self.run(command='openssl passwd -crypt {0}'.format(tmp_password))
            self.run(command='sudo adduser -p {0} {1}'.format(encrypted_password.split()[-1], new_username))  # encrypted password may contain Warning
            self.run(command='sudo echo "{0} ALL=(root) NOPASSWD:ALL" | tee -a /etc/sudoers.d/{0}'.format(new_username))
            self.run(command='sudo chmod 0440 /etc/sudoers.d/{0}'.format(new_username))
        self.set_ssh_creds(username=new_username, password=tmp_password)
        with open(with_config.KEY_PUBLIC_PATH) as f:
            self.put_string_as_file_in_dir(string_to_put=f.read(), file_name='authorized_keys', in_directory='.ssh')
        self.run(command='sudo chmod 700 .ssh')
        self.run(command='sudo chmod 600 .ssh/authorized_keys')
        self.set_ssh_creds(username=new_username, password='ssh_key')

    def ping(self, port=22):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        try:
            s.connect((str(self.get_ssh_ip()), port))
            res = True
        except (socket.timeout, socket.error):
            res = False
        finally:
            s.close()
        return res
    
    def actuate_hostname(self, refresh=True):
        if not hasattr(self, '_hostname') or refresh:
            self._hostname = self.run('hostname').stdout.strip()
        return self._hostname

    def form_mac(self, mac_pattern):
        return '00:{lab:02}:00:{role_id}:{count:02}:{net}'.format(lab=self._lab.get_id(), role_id=self.lab().ROLES[self.get_role()], count=self._n, net=mac_pattern)

    def list_ip_info(self, connection_attempts=100):
        ans_a = self.run('ip -o a', connection_attempts=connection_attempts, warn_only=True)
        if not ans_a:
            return {}
        ans_l = self.run('ip -o l', connection_attempts=connection_attempts, warn_only=True)
        name_ipv4_ipv6 = {}
        for line in ans_a.split('\n'):
            _, nic_name, other = line.split(' ', 2)
            name_ipv4_ipv6.setdefault(nic_name, {'ipv4': None, 'ipv6': None})
            if 'inet6' in other:
                name_ipv4_ipv6[nic_name]['ipv6'] = other.split()[1].strip()
            else:
                name_ipv4_ipv6[nic_name]['ipv4'] = other.split()[1].strip()

        result = {}
        for line in ans_l.split('\n'):
            number, nic_name, other = line.split(':', 2)
            nic_name = nic_name.strip()
            if nic_name == 'lo':
                continue
            status, mac_part = other.split('link/ether')
            mac = mac_part.split(' brd ')[0].strip()
            ipv4 = name_ipv4_ipv6.get(nic_name, {'ipv4': None})['ipv4']
            ipv6 = name_ipv4_ipv6.get(nic_name, {'ipv6': None})['ipv6']
            result[nic_name] = {'mac': mac.upper(), 'ipv4': ipv4, 'ipv6': ipv6}
        return result

    def is_nics_correct(self):
        actual_nics = self.list_ip_info(connection_attempts=1)
        if not actual_nics:
            return False

        for nic in self.get_nics().values():
            mac = nic.get_mac()  # be careful : after bonding all interfaces of the bond get mac of the first one
            ip, _ = nic.get_ip_and_mask()
            prefix_len = nic.get_net().prefixlen
            ip = ip + '/' + str(prefix_len)
            master_nic_name = nic.get_name()
            if master_nic_name not in actual_nics:
                self.log(message='has no master NIC {}'.format(master_nic_name), level='warning')
                return False
            actual_ip = actual_nics[master_nic_name]['ipv4']
            if nic.is_pxe() == False and ip != actual_ip:  # this ip might be re-assign to the bridge which has this NIC inside
                self.log(message='NIC "{}" has different IP  actual: {}  requested: {}'.format(nic.get_name(), actual_ip, ip), level='warning')
                return False
            for slave_nic_name, _ in sorted(nic.get_slave_nics().items()):
                if slave_nic_name not in actual_nics:
                    self.log(message='has no slave NIC {}'.format(slave_nic_name), level='warning')
                    return False
                actual_mac = actual_nics[slave_nic_name]['mac'].upper()
                if actual_mac != mac.upper():
                    self.log(message='NIC {} has different mac: actual {} requested {}'.format(slave_nic_name, actual_mac, mac), level='warning')
                    return False
        return True

    def register_rhel(self, rhel_subscription_creds_url):
        import requests
        import json

        text = requests.get(rhel_subscription_creds_url).text
        rhel_json = json.loads(text)
        rhel_username = rhel_json['rhel-username']
        rhel_password = rhel_json['rhel-password']
        rhel_pool_id = rhel_json['rhel-pool-id']

        repos_to_enable = ['--enable=rhel-7-server-rpms',
                           '--enable=rhel-7-server-optional-rpms',
                           '--enable=rhel-7-server-extras-rpms',
                           '--enable=rhel-7-server-openstack-7.0-rpms',
                           '--enable=rhel-7-server-openstack-7.0-director-rpms']
        status = self.run(command='subscription-manager status', warn_only=True)
        if 'Overall Status: Current' not in status:
            self.run(command='sudo subscription-manager register --force --username={0} --password={1}'.format(rhel_username, rhel_password))
            available_pools = self.run(command='sudo subscription-manager list --available')
            if rhel_pool_id not in available_pools:
                raise ValueError('Provided RHEL pool id "{}" is not in the list of available pools, plz check your RHEL credentials here {}'.format(rhel_pool_id, rhel_subscription_creds_url))

            self.run(command='sudo subscription-manager attach --pool={0}'.format(rhel_pool_id))
            self.run(command='sudo subscription-manager repos --disable=*')
            self.run(command='sudo subscription-manager repos ' + ' '.join(repos_to_enable))
