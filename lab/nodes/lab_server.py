from lab.nodes import LabNode


class LabServer(LabNode):

    def __init__(self, **kwargs):
        super(LabServer, self).__init__(**kwargs)

        self._tmp_dir_exists = False
        self._package_manager = None
        self._mac_server_part = None
        self.__server = None
        self._virtual_servers = set()  # virtual servers running on this hardware server

    def add_virtual_server(self, server):
        self._virtual_servers.add(server)

    @property
    def _server(self):
        from lab.server import Server

        if self.__server is None:
            self.__server = Server(ip=self.get_ssh_ip(), username=self._ssh_username, password=self._ssh_password)
        return self.__server

    def cmd(self, cmd):
        raise NotImplementedError

    def get_nic(self, nic):
        try:
            return self._nics[nic]
        except KeyError:
            return RuntimeError('{}: is not on {} network'.format(self.get_node_id(), nic))

    def add_nics(self, nics_cfg):
        from lab.network import Nic

        self._nics = Nic.add_nics(node=self, nics_cfg=nics_cfg)

    def get_ssh_ip(self):
        return [x for x in self._nics.values() if x.is_ssh()][0].get_ip_and_mask()[0]

    def get_nics(self):
        return self._nics

    def get_ip_api(self):
        return self.get_nic('a').get_ip_and_mask()[0]

    def get_ip_api_with_prefix(self):
        return self.get_nic('a').get_ip_with_prefix()

    def get_ip_mx(self):
        return self.get_nic('mx').get_ip_and_mask()[0]

    def get_ip_mx_with_prefix(self):
        return self.get_nic('mx').get_ip_with_prefix()

    def get_gw_mx_with_prefix(self):
        return self.get_nic('mx').get_gw_with_prefix()

    def get_ip_t(self):
        return self.get_nic('t').get_ip_and_mask()[0]

    def get_ip_t_with_prefix(self):
        return self.get_nic('t').get_ip_with_prefix()

    def get_ssh_for_bash(self):
        ip, u, p = self.get_ssh()
        command = 'sshpass -p {} ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no {}@{}'.format(p, u, ip)
        if self._proxy:
            command = self._proxy.get_ssh_for_bash()[0].replace('ssh ', 'ssh -t ') + ' ' + command
        return command, super(LabServer, self).get_ssh_for_bash()

    def set_hostname(self, hostname):
        self._server.set_hostname(hostname=hostname)

    def get_hostname(self):
        return self._server.get_hostname()

    def get_ssh(self):
        return self._server.get_ssh()

    def r_is_nics_correct(self):
        actual_nics = self._server.r_list_ip_info(connection_attempts=1)
        if not actual_nics:
            return False

        status = True
        for main_name, nic in self.get_nics().items():
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

        ip, username, password = self._server.get_ssh()
        if 'sudo' in command and 'sudo -p "" -S ' not in command:
            command = command.replace('sudo ', 'echo {} | sudo -p "" -S '.format(password))

        if estimated_time:
            self.log('Running {}... (usually it takes {} secs)'.format(command, estimated_time))
        started_at = time.time()
        if self._proxy:
            while True:
                ans = self._proxy.exe(command="sshpass -p {} ssh -o StrictHostKeyChecking=no {}@{} '{}' # run on {}".format(password, username, ip, command, self.get_node_id()), in_directory=in_directory, is_warn_only=True)
                if 'No route to host' in ans:
                    if connection_attempts == 0:
                        raise RuntimeError('Can not execute {} since {}'.format(command, ans))
                    connection_attempts -= 1
                    time.sleep(10)
                    continue
                else:
                    break
        else:
            ans = self._server.exe(command=command, in_directory=in_directory, is_warn_only=is_warn_only, connection_attempts=connection_attempts)
        if estimated_time:
            self.log('{} finished and actually took {} secs'.format(command, time.time() - started_at))
        return ans

    def file_append(self, file_path, data, in_directory='.', is_warn_only=False, connection_attempts=100):
        if self._proxy:
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

    def r_install_sshpass_openvswitch_expect(self):
        for rpm, checksum in ['sshpass-1.06-1.el7.rf.x86_64.rpm', 'openvswitch-2.5.0-1.el7.centos.x86_64.rpm']:
            local_path, _ = self.r_get_remote_file(url='http://172.29.173.233/redhat/{}'.format(rpm))
            self.exe(command='rpm -i {}'.format(local_path), is_warn_only=True)
            self.exe(command='rm -f {}'.format(local_path))
        self.exe('yum install -q -y expect')

    def r_get_remote_file(self, url, to_directory='.'):
        return self._server.r_get_remote_file(url, to_directory=to_directory)

    def r_get_file_from_dir(self, file_name, in_directory='.', local_path=None):
        return self._server.r_get_file_from_dir(file_name=file_name, in_directory=in_directory, local_path=local_path)

    def r_clone_repo(self, repo_url, local_repo_dir=None, tags=None, patch=None):
        return self._server.clone_repo(repo_url, local_repo_dir, tags, patch)

    def r_put_string_as_file_in_dir(self, string_to_put, file_name, in_directory='.'):
        return self._server.put_string_as_file_in_dir(string_to_put, file_name, in_directory=in_directory)

    def r_is_online(self):
        if self._proxy:
            ans = self._proxy.exe(command='ping -c 1 {}'.format(self._server.get_ssh()[0]), is_warn_only=True)
            return '1 received, 0% packet loss' in ans
        else:
            return self._server.ping()

    def r_list_ip_info(self):
        return self._server.r_list_ip_info()
