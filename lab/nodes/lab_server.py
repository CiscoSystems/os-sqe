from lab.nodes import LabNode


class LabServer(LabNode):

    def __init__(self, node_id, role, lab):
        self._tmp_dir_exists = False
        self._package_manager = None
        self._mac_server_part = None
        self._proxy_server = None
        self._server = None

        super(LabServer, self).__init__(node_id=node_id, role=role, lab=lab)

    def cmd(self, cmd):
        raise NotImplementedError

    def get_ssh_for_bash(self):
        ip, u, p = self.get_ssh()
        command = 'sshpass -p {} ssh {}@{}'.format(p, u, ip)
        if self._proxy_server:
            command = self._proxy_server.get_ssh_for_bash().replace('ssh ', 'ssh -t ') + ' ' + command
        return command

    def set_proxy_server(self, proxy):
        self._proxy_server = proxy

    def set_ssh_creds(self, username, password):
        from lab.server import Server

        self._server = Server(ip=self.get_oob()[0], username=username, password=password)

    def set_hostname(self, hostname):
        self._server.set_hostname(hostname=hostname)

    def get_hostname(self):
        return self._server.get_hostname()

    def get_ssh(self):
        return self._server.get_ssh()

    def add_nic(self, nic_name, ip_or_index, net, on_wires, is_ssh):
        import validators
        from lab.network import Nic

        ip_or_index = ip_or_index or self._assign_default_ip_index(net)

        try:
            index = int(ip_or_index)  # this is shift in the network
            if index in [0, 1, 2, 3, -1]:
                raise IndexError('{}:  index={} is not possible since 0 =>  network address [1,2,3] => GW addresses -1 => broadcast address'.format(self.get_node_id(), index))
            try:
                net.get_ip_for_index(index)
            except (IndexError, ValueError):
                raise IndexError('{}: index {} is out of bound of {}'.format(self.get_node_id(), index, net))
        except ValueError:
            if validators.ipv4(str(ip_or_index)):
                try:
                    index, ip = {x: str(net.get_ip_for_index(x)) for x in range(net.get_size()) if str(ip_or_index) in str(net.get_ip_for_index(x))}.items()[0]
                except IndexError:
                    raise ValueError('{}: ip {} is out of bound of {}'.format(self.get_node_id(), ip_or_index, net))
            else:
                raise ValueError('{}: specified value "{}" is neither ip nor index in network'.format(self.get_node_id(), ip_or_index))

        nic = Nic(name=nic_name, node=self, net=net, net_index=index, on_wires=on_wires, is_ssh=is_ssh)
        self._nics[nic_name] = nic
        if is_ssh:
            self._server.set_ssh_ip(ip=nic.get_ip_and_mask()[0])
        return nic

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
        if self._proxy_server:
            while True:
                ans = self._proxy_server.exe(command="sshpass -p {} ssh -o StrictHostKeyChecking=no {}@{} '{}' # run on {}".format(password, username, ip, command, self.get_node_id()), in_directory=in_directory, is_warn_only=True)
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
        if self._proxy_server:
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
        for rpm in ['sshpass-1.05-1.el7.rf.x86_64.rpm', 'openvswitch-2.5.0-1.el7.centos.x86_64.rpm']:
            local_path = self.r_get_remote_file(url='http://172.29.173.233/redhat/{}'.format(rpm))
            self.exe(command='rpm -i {}'.format(local_path), is_warn_only=True)
            self.exe(command='rm -f {}'.format(local_path))
        self.exe('yum install -q -y expect')

    def r_get_remote_file(self, url, to_directory='.', checksum=None, method='md5sum'):
        return self._server.wget_file(url, to_directory=to_directory, checksum=checksum, method=method)

    def r_put_string_as_file_in_dir(self, string_to_put, file_name, in_directory='.'):
        return self._server.put_string_as_file_in_dir(string_to_put, file_name, in_directory=in_directory)

    def r_is_online(self):
        if self._proxy_server:
            ans = self._proxy_server.exe(command='ping -c 1 {}'.format(self._server.get_ssh()[0]), is_warn_only=True)
            return '1 received, 0% packet loss' in ans
        else:
            return self._server.ping()

    def r_list_ip_info(self):
        return self._server.r_list_ip_info()
