from lab.nodes import LabNode


class LabServer(LabNode):

    def __init__(self, pod, dic):
        from lab.network import Nic

        super(LabServer, self).__init__(pod=pod, dic=dic)

        self.ssh_username, self.ssh_password = dic['ssh-username'], dic.get('ssh-password', None)  # if password is None - use sqe ssh key
        self._package_manager = None
        self.__server = None  # lazy initialisation to lab.server.Server instance
        self.virtual_servers = set()  # virtual servers running on this hardware server
        self.nics = Nic.add_nics(node=self, nics_cfg=dic['nics'])

    def add_virtual_server(self, server):
        self.virtual_servers.add(server)

    @property
    def _server(self):
        from lab.server import Server

        if self.__server is None:
            if self.proxy:
                self.__server = Server(ip=self.proxy.ssh_ip, username=self.proxy.ssh_username, password=self.proxy.ssh_password)
                self.__server.via_proxy = 'ssh -o StrictHostKeyChecking=no ' + self.id
            else:
                self.__server = Server(ip=self.ssh_ip, username=self.ssh_username, password=self.ssh_password)

        return self.__server

    def cmd(self, cmd):
        raise NotImplementedError

    def get_nic(self, nic):
        try:
            return self.nics[nic]
        except KeyError:
            raise RuntimeError('{}: is not on network "{}"'.format(self.id, nic))

    @property
    def ssh_ip(self):
        return [x for x in self.nics.values() if x.is_ssh][0].ip

    @property
    def api_ip(self):
        return self.get_nic('a').ip

    @property
    def api_ip_with_prefix(self):
        return self.get_nic('a').ip_with_prefix

    @property
    def mx_ip(self):
        return self.get_nic('m').ip

    def get_ip_mx_with_prefix(self):
        return self.get_nic('m').get_ip_with_prefix()

    def get_gw_mx_with_prefix(self):
        return self.get_nic('m').get_gw_with_prefix()

    def get_ip_t(self):
        return self.get_nic('t').get_ip_and_mask()[0]

    def get_ip_t_with_prefix(self):
        return self.get_nic('t').get_ip_with_prefix()

    def set_hostname(self, hostname):
        self._server.set_hostname(hostname=hostname)

    def r_get_hostname(self):
        return self._server.r_get_hostname()

    def r_is_nics_correct(self):
        actual_nics = self._server.r_list_ip_info(connection_attempts=1)
        if not actual_nics:
            return False

        status = True
        for main_name, nic in self.nics.items():
            requested_mac = nic.get_macs()[0].lower()
            requested_ip = nic.get_ip_with_prefix()
            if len(nic.get_names()) > 1:
                requested_name_with_ip = [main_name, 'br-' + main_name]
            else:
                requested_name_with_ip = nic.get_names()

            if not nic.is_pxe():
                if requested_ip not in actual_nics:
                    self.log(message='{}: requested IP {} is not assigned, actually it has {}'.format(main_name, requested_ip, actual_nics.get(requested_name_with_ip, {}).get('ipv4', 'None')), level='warning')
                    status = False
                else:
                    iface = actual_nics[requested_ip][0]
                    if iface not in requested_name_with_ip:  # might be e.g. a or br-a
                        self.log(message='requested IP {} is assigned to "{}" while supposed to be one of "{}"'.format(requested_ip, iface, requested_name_with_ip), level='warning')
                        status = False

            if requested_mac not in actual_nics:
                self.log(message='{}: requested MAC {} is not assigned, actually it has {}'.format(main_name, requested_mac, actual_nics.get(main_name, {}).get('mac', 'None')), level='warning')
                status = False
        return status

    def exe(self, command, in_directory='.', is_warn_only=False, connection_attempts=100, estimated_time=None):
        import time

        if estimated_time:
            self.log('Running {}... (usually it takes {} secs)'.format(command, estimated_time))
        started_at = time.time()
        ans = self._server.exe(command=command, in_directory=in_directory, is_warn_only=is_warn_only, connection_attempts=connection_attempts)
        if estimated_time:
            self.log('{} finished and actually took {} secs'.format(command, time.time() - started_at))
        return ans

    def exe_as_sqe(self, cmd, in_dir='.', is_warn_only=False, connection_attempts=100, estimated_time=None):
        from lab.server import Server

        import time

        if estimated_time:
            self.log('Running {} as sqe user... (usually it takes {} secs)'.format(cmd, estimated_time))
        started_at = time.time()
        ans = Server(ip=self.ssh_ip, username='sqe', password=None).exe(command=cmd, in_directory=in_dir, is_warn_only=is_warn_only, connection_attempts=connection_attempts)
        if estimated_time:
            self.log('{} finished and actually took {} secs'.format(cmd, time.time() - started_at))
        return ans

    def get_as_sqe(self, rem_rel_path, in_dir, loc_abs_path):
        from lab.server import Server

        return Server(ip=self.ssh_ip, username='sqe', password=None).get(rem_rel_path, in_dir, loc_abs_path)

    def file_append(self, file_path, data, in_directory='.', is_warn_only=False, connection_attempts=100):
        if self.proxy:
            raise NotImplemented
        else:
            ans = self._server.file_append(file_path=file_path, data=data, in_directory=in_directory, is_warn_only=is_warn_only, connection_attempts=connection_attempts)
        return ans

    def r_register_rhel(self, rhel_subscription_creds_url):
        import requests
        import json

        text = requests.get(rhel_subscription_creds_url).text
        rhel_json = json.loads(text)
        rhel_username = rhel_json['rhel-username']
        rhel_password = rhel_json['rhel-password']
        rhel_pool_id = rhel_json['rhel-pool-id']

        repos_to_enable = ' '.join(['--enable=rhel-7-server-rpms',
                                    '--enable=rhel-7-server-optional-rpms',
                                    '--enable=rhel-7-server-extras-rpms',
                                    # '--enable=rhel-7-server-openstack-7.0-rpms', '--enable=rhel-7-server-openstack-7.0-director-rpms'
                                    ])

        self.exe(command='subscription-manager register --force --username={0} --password={1}'.format(rhel_username, rhel_password))
        self.exe(command='subscription-manager attach --pool={}'.format(rhel_pool_id))
        self.exe(command='subscription-manager repos --disable=*')
        self.exe(command='subscription-manager repos {}'.format(repos_to_enable))

    def r_clone_repo(self, repo_url, local_repo_dir=None, tags=None, patch=None):
        local_repo_dir = local_repo_dir or repo_url.split('/')[-1].strip('.git')

        # self.check_or_install_packages(package_names='git')
        self.exe_as_sqe(cmd='test -d {0} || git clone -q {1} {0}'.format(local_repo_dir, repo_url))
        repo_abs_path = self.exe_as_sqe(cmd='git pull -q && pwd', in_dir=local_repo_dir)
        if patch:
            self.exe_as_sqe(cmd='git fetch {0} && git checkout FETCH_HEAD'.format(patch))
        elif tags:
            self.exe_as_sqe(cmd='git checkout tags/{0}'.format(tags), in_dir=local_repo_dir)
        return repo_abs_path

    def r_curl(self, url, size, checksum, loc_abs_path):
        from os import path

        if loc_abs_path[0] not in ['/', '~']:
            raise ValueError('loc_abs_path needs to be full path')
        url = url.strip().strip('\'')
        info_url = url + '.txt'

        cache_abs_path = path.join('/tmp', path.basename(loc_abs_path))

        if path.dirname(loc_abs_path) not in ['~', '.', '/tmp', '/var/tmp', '/var', '/root']:
            self.exe_as_sqe('mkdir -p {0}'.format(path.dirname(loc_abs_path)))

        while True:
            self.exe_as_sqe('test -e {c} || curl --silent --remote-time {url} -o {c}'.format(c=cache_abs_path, url=url))  # download to cache directory and use as cache
            actual_checksum = self.exe_as_sqe('{} {}'.format('sha256sum' if len(checksum) == 64 else 'md5sum', cache_abs_path)).split()[0]
            if actual_checksum == checksum:
                break
            else:
                actual_size = self.exe_as_sqe('ls -la {}'.format(cache_abs_path)).split()[4]
                if int(size) - int(actual_size) > 0:  # probably curl fails to download up to the end, repeat it
                    self.exe_as_sqe('rm -f {}'.format(cache_abs_path))
                    continue
                else:
                    raise RuntimeError('image described here {}.txt has wrong checksum. Check it manually'.format(url))

        self.exe_as_sqe('rm -f {l} && cp {c} {l}'.format(l=loc_abs_path, c=cache_abs_path))

    def r_get_file_from_dir(self, rem_rel_path, in_dir='.', loc_abs_path=None):
        """Get remote file as string or local file if local_path is specified
        :param rem_rel_path: relative path to remote file from specified in_dir
        :param in_dir: absolute or relative to ~ path to remote folder
        :param loc_abs_path: absolute path to local file to be created 
        :return: local abs path or file body
        """
        if loc_abs_path:
            return self.get_as_sqe(rem_rel_path, in_dir, loc_abs_path)
        else:
            return self.exe_as_sqe(cmd='sudo cat ' + rem_rel_path, in_dir=in_dir)

    def r_put_string_to_file_in_dir(self, string_to_put, rem_rel_path, in_dir='.'):
        if '/' in rem_rel_path:
            raise SyntaxError('rem_rel_path can not contain /, use in_dir instead')

        sudo = 'sudo ' if in_dir.startswith('/') else ''

        if in_dir not in ['.', '~', '/var', '/tmp', '/var/tmp']:
            self.exe_as_sqe(cmd=sudo + 'mkdir -p ' + in_dir)
        self.exe_as_sqe(cmd=sudo + 'echo ' + string_to_put + ' > ' + rem_rel_path, in_dir=in_dir)

    def r_is_online(self):
        if self._proxy:
            ans = self._proxy.exe(command='ping -c 1 {}'.format(self._server.get_ssh()[0]), is_warn_only=True)
            return '1 received, 0% packet loss' in ans
        else:
            return self._server.ping()

    def r_list_ip_info(self):
        return self._server.r_list_ip_info()

    def r_get_n_sriov(self):
        return len([x for x in self.exe('lspci | grep 710').split('\n') if 'Virtual' in x])
