from lab.nodes import LabNode


class LabServer(LabNode):

    def __init__(self, pod, dic):
        from lab.network import Nic

        super(LabServer, self).__init__(pod=pod, dic=dic)

        self.ssh_ip, self.ssh_username, self.ssh_password = dic['ssh-ip'], dic['ssh-username'], dic['ssh-password']  # if password is None - use sqe ssh key
        self._package_manager = None
        self.virtual_servers = set()  # virtual servers running on this hardware server
        self.nics_dic = Nic.create_nics_dic(node=self, dics_lst=dic['nics']) or {}

    def add_virtual_server(self, server):
        self.virtual_servers.add(server)

    def cmd(self, cmd):
        raise NotImplementedError

    def r_list_ip_info(self, n_attempts=100):
        ans = self.exe(cmd='ip -o a && ip -o l && echo SEPARATOR && ip -o r && echo SEPARATOR && cat /etc/hosts', n_attempts=n_attempts, is_warn_only=True)
        if not ans:
            return {}
        result = {'ips': {}, 'macs': {}, 'etc_hosts': {}, 'ifaces': {}, 'networks': {}}

        ip_o_al, ip_o_r, cat_etc_hosts = ans.split('SEPARATOR')
        for line in ip_o_al.split('\r\n')[:-1]:
            split = line.split()
            iface_name = split[1].strip(':')
            iface_dic = result['ifaces'].setdefault(iface_name, {'ipv4': [], 'ipv6': [], 'cidr': None, 'mac': None, 'is-ssh': False, 'master': None, 'slaves': []})
            if 'inet' in line:
                ip = split[3]
                iface_dic['ipv6' if 'inet6' in split else 'ipv4'].append(ip)
                result['ips'][ip] = iface_name
            elif 'link/' in line:
                mac = split[-3]
                iface_dic['mac'] = mac
                result['macs'][mac] = iface_name
        for line in ip_o_r.split('\r\n')[1:-1]:
            split = line.split()
            cidr = split[0]
            if cidr == 'default':  # default route
                result['gw'] = split[2]
                result['ifaces'][split[4]]['is-ssh'] = True
            elif cidr == '169.254.0.0/16':
                continue
            else:
                iface_name = split[2]
                result['networks'][cidr] = iface_name
                result['ifaces'][iface_name]['cidr'] = cidr
        # for line in brctl_show.split('\r\n')[2:]:
        #     if line:
        #         br_name, br_id_stp, ifaces = line.split('\t\t')
        #         if ifaces:
        #             result['ifaces'][br_name]['slaves'].append(ifaces)
        #             result['ifaces'][ifaces]['master'] = br_name
        result['etc_hosts'] = {x.split()[1]: x.split()[0] for x in cat_etc_hosts.split('\r\n') if x}
        return result

    def r_is_nics_correct(self):
        actual_nics = self.r_list_ip_info(n_attempts=1)
        if not actual_nics:
            return False

        status = True
        for main_name, nic in self.nics_dic.items():
            requested_mac = nic.get_macs()[0].lower()
            requested_ip = nic.get_ip_with_prefix()
            if len(nic.get_names()) > 1:
                requested_name_with_ip = [main_name, 'br-' + main_name]
            else:
                requested_name_with_ip = nic.get_names()

            if not nic.is_pxe():
                if requested_ip not in actual_nics:
                    self.log_warning(message='{}: requested IP {} is not assigned, actually it has {}'.format(main_name, requested_ip, actual_nics.get(requested_name_with_ip, {}).get('ipv4', 'None')))
                    status = False
                else:
                    iface = actual_nics[requested_ip][0]
                    if iface not in requested_name_with_ip:  # might be e.g. a or br-a
                        self.log_warning(message='requested IP {} is assigned to "{}" while supposed to be one of "{}"'.format(requested_ip, iface, requested_name_with_ip))
                        status = False

            if requested_mac not in actual_nics:
                self.log_warning(message='{}: requested MAC {} is not assigned, actually it has {}'.format(main_name, requested_mac, actual_nics.get(main_name, {}).get('mac', 'None')))
                status = False
        return status

    def exe(self, cmd, in_dir='.', is_warn_only=False, is_as_sqe=False, n_attempts=100, estimated_time=None):
        import time
        from lab.server import Server

        ip, username, password = (self.proxy.ssh_ip, self.proxy.ssh_username, self.proxy.ssh_password) if self.proxy else (self.ssh_ip, self.ssh_username, self.ssh_password)
        if is_as_sqe:
            username, password = self.SQE_USERNAME, None
            self.pod.check_create_sqe_user()
        srv = Server(ip=ip, username=username, password=password)

        comment = ' # ' + self.pod.name + ' ' + self.id + ':'
        comment += ' sshpass -p ' + password if password else ''
        comment += ' ssh ' + username + '@' + ip

        if 'sudo' in cmd and 'sudo -p "" -S ' not in cmd:
            cmd = cmd.replace('sudo ', 'echo {} | sudo -p "" -S '.format(self.ssh_password))
        if self.proxy:
            cmd = 'ssh -o StrictHostKeyChecking=no ' + self.id + ' "{}"'.format(cmd)
            comment += ' ssh ' + self.id

        if estimated_time:
            self.log('Running {}... (usually it takes {} secs)'.format(cmd, estimated_time))
        started_at = time.time()
        ans = srv.exe(cmd=cmd + comment, in_dir=in_dir, is_warn_only=is_warn_only, n_attempts=n_attempts)
        if estimated_time:
            self.log('{} finished and actually took {} secs'.format(cmd, time.time() - started_at))
        return ans

    def get_as_sqe(self, rem_rel_path, in_dir, loc_abs_path):
        from lab.server import Server

        return Server(ip=self.ssh_ip, username='sqe', password=None).get(rem_rel_path, in_dir, loc_abs_path)

    def file_append(self, file_path, data, in_directory='.', is_warn_only=False, n_attempts=100):
        from lab.server import Server

        if self.proxy:
            raise NotImplemented()
        else:
            ans = Server(ip=self.ssh_ip, username=self.ssh_username, password=self.ssh_password).file_append(file_path=file_path, data=data, in_directory=in_directory, is_warn_only=is_warn_only, n_attempts=n_attempts)
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

        self.exe(cmd='subscription-manager register --force --username={0} --password={1}'.format(rhel_username, rhel_password))
        self.exe(cmd='subscription-manager attach --pool={}'.format(rhel_pool_id))
        self.exe(cmd='subscription-manager repos --disable=*')
        self.exe(cmd='subscription-manager repos {}'.format(repos_to_enable))

    def r_clone_repo(self, repo_url, local_repo_dir=None, tags=None, patch=None):
        local_repo_dir = local_repo_dir or repo_url.split('/')[-1].strip('.git')

        # self.check_or_install_packages(package_names='git')
        self.exe(cmd='test -d {0} || git clone -q {1} {0}'.format(local_repo_dir, repo_url), is_as_sqe=True)
        repo_abs_path = self.exe(cmd='git pull -q && pwd', in_dir=local_repo_dir, is_as_sqe=True)
        if patch:
            self.exe(cmd='git fetch {0} && git checkout FETCH_HEAD'.format(patch), is_as_sqe=True)
        elif tags:
            self.exe(cmd='git checkout tags/{0}'.format(tags), in_dir=local_repo_dir, is_as_sqe=True)
        return repo_abs_path

    def r_curl(self, url, size, checksum, loc_abs_path):
        from os import path

        if loc_abs_path[0] not in ['/', '~']:
            raise ValueError('loc_abs_path needs to be full path')
        url = url.strip().strip('\'')

        cache_abs_path = path.join('/tmp', path.basename(loc_abs_path))

        if path.dirname(loc_abs_path) not in ['~', '.', '/tmp', '/var/tmp', '/var', '/root']:
            self.exe('mkdir -p {0}'.format(path.dirname(loc_abs_path)), is_as_sqe=True)

        while True:
            self.exe('test -e {c} || curl --silent --remote-time {url} -o {c}'.format(c=cache_abs_path, url=url), is_as_sqe=True)  # download to cache directory and use as cache
            actual_checksum = self.exe('{} {}'.format('sha256sum' if len(checksum) == 64 else 'md5sum', cache_abs_path), is_as_sqe=True).split()[0]
            if actual_checksum == checksum:
                break
            else:
                actual_size = self.exe('ls -la {}'.format(cache_abs_path), is_as_sqe=True).split()[4]
                if int(size) - int(actual_size) > 0:  # probably curl fails to download up to the end, repeat it
                    self.exe('rm -f {}'.format(cache_abs_path), is_as_sqe=True)
                    continue
                else:
                    raise RuntimeError('image described here {}.txt has wrong checksum. Check it manually'.format(url))

        self.exe('rm -f {l} && cp {c} {l}'.format(l=loc_abs_path, c=cache_abs_path), is_as_sqe=True)

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
            return self.exe(cmd='sudo cat ' + rem_rel_path, in_dir=in_dir, is_as_sqe=True)

    def r_put_string_to_file_in_dir(self, string_to_put, rem_rel_path, in_dir='.'):
        if '/' in rem_rel_path:
            raise SyntaxError('rem_rel_path can not contain /, use in_dir instead')

        sudo = 'sudo ' if in_dir.startswith('/') else ''

        if in_dir not in ['.', '~', '/var', '/tmp', '/var/tmp']:
            self.exe(cmd=sudo + 'mkdir -p ' + in_dir, is_as_sqe=True)
        self.exe(cmd=sudo + 'echo ' + string_to_put + ' > ' + rem_rel_path, in_dir=in_dir)

    def r_is_online(self):
        import socket

        if self.proxy:
            ans = self.proxy.exe(cmd='ping -c 1 {}'.format(self.ssh_ip), is_warn_only=True)
            return '1 received, 0% packet loss' in ans
        else:
            port = 22
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            try:
                s.connect((self.ssh_ip, port))
                res = True
            except (socket.timeout, socket.error):
                res = False
            finally:
                s.close()
            return res

    def r_get_n_sriov(self):
        return len([x for x in self.exe('lspci | grep 710', is_warn_only=True).split('\n') if 'Virtual' in x])
