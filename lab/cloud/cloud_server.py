from lab.with_log import WithLogMixIn
from lab.cloud import CloudObject


class CloudServer(CloudObject, WithLogMixIn):
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_BUILD = 'BUILD'
    STATUS_DELETED = 'DELETED'
    STATUS_SUSPENDED = 'SUSPENDED'
    STATUS_VERIFY_RESIZE = 'VERIFY_RESIZE'

    def __repr__(self):
        return self.name + '@' + str(self.compute) + ' ' + self.status

    def __init__(self, cloud, dic):
        super(CloudServer, self).__init__(cloud=cloud, dic=dic)
        self.ips = [x.split('=')[-1] for x in dic['addresses'].split(',')]
        self.srv_ip = self.ips[0]
        if dic.get('image'):
            self.image = [x for x in self.cloud.images if x.id == dic['image'].split()[-1].strip('()')][0]
            self.srv_username = self.image.username
            self.srv_password = self.image.password
        self._srv_serial = None

    @property
    def srv_libvirt(self):
        return self.dic_from_os['OS-EXT-SRV-ATTR:instance_name']

    @property
    def compute(self):
        comp_candidates = filter(lambda c: c.name == self.dic_from_os['OS-EXT-SRV-ATTR:host'], self.cloud.computes)
        return comp_candidates[0] if comp_candidates else None

    @property
    def srv_serial(self):
        if not self._srv_serial:
            grep = self.compute.host_exe('libvirt virsh dumpxml ' + self.srv_libvirt + ' | grep "source mode="')
            self._srv_serial = grep.split('service=\'')[-1].split('\'')[0]
        return self._srv_serial

    @staticmethod
    def wait(cloud, srv_id_name_dic, status, timeout=100):
        import time

        if not srv_id_name_dic:
            return
        required_n_servers = 0 if status == CloudServer.STATUS_DELETED else len(srv_id_name_dic)
        start_time = time.time()
        while True:
            a = cloud.os_cmd(cmds=['openstack server list --long -f json'])
            our = filter(lambda x: x['ID'] in srv_id_name_dic, a[0])
            in_error = filter(lambda x: x['Status'] == 'ERROR', our)
            in_status = filter(lambda x: x['Status'] == status, our) if status != CloudServer.STATUS_DELETED else our
            if len(in_status) == required_n_servers:
                return in_status  # all successfully reached the status
            if in_error:
                CloudServer.analyse_servers_problems(servers=in_error)
                raise RuntimeError('These instances failed: {0}'.format(in_error))
            if time.time() > start_time + timeout:
                CloudServer.analyse_servers_problems(servers=our)
                raise RuntimeError('Instances {} are not {} after {} secs'.format(our, status, timeout))
            time.sleep(15)

    @staticmethod
    def analyse_servers_problems(servers):
        for srv in servers:
            srv.compute.exe('pkill -f ' + srv.libvirt_name)
            srv.cloud.pod.r_collect_info(regex=srv.id, comment='fail-of-' + srv.name)

    @staticmethod
    def create(how_many, flavor, image, key, on_nets, timeout, cloud):
        from lab.cloud.cloud_port import CloudPort

        srv_id_name_dic = {}
        for n, comp in [(y, cloud.computes[y % len(cloud.computes)]) for y in range(1, how_many + 1)]:  # distribute servers per compute host in round robin
            ports = CloudPort.create(cloud=cloud, server_number=n, on_nets=on_nets)
            ports_part = ' '.join(map(lambda x: '--nic port-id=' + x.id, ports))
            name = CloudObject.UNIQUE_PATTERN_IN_NAME + str(n)
            cmd = 'openstack server create {} --flavor {} --image "{}" --availability-zone nova:{} --security-group default --key-name {} {} -f json'.format(name, flavor.name, image.name, comp.name, key.name, ports_part)
            dic = cloud.os_cmd([cmd])
            srv_id_name_dic[dic[0]['id']] = dic[0]['name']
        CloudServer.wait(cloud=cloud, srv_id_name_dic=srv_id_name_dic, status=CloudServer.STATUS_ACTIVE, timeout=timeout)
        a = cloud.os_cmd(['for id in {}; do openstack server show $id -f json; done'.format(' '.join(srv_id_name_dic.keys()))])
        return map(lambda x: CloudServer(cloud=cloud, dic=x), a)

    def migrate(self, how):
        import time

        other_compute = [x for x in self.cloud.computes if x != self.compute][0]
        live_option = '--live ' + other_compute.name if how == 'live' else '--block-migration'
        msg = '{} {} migrating from {}{}'.format(time.strftime('%b%d %H:%M:%S'), how, self.compute, ' to {}'.format(other_compute) if how == 'live' else '')
        self.console_exe('echo {} >> migration_history'.format(msg))
        self.cloud.os_cmd(['openstack server migrate {} {} '.format(live_option, self.name)])
        self.wait(cloud=self.cloud, srv_id_name_dic={self.id: self.name}, status=self.STATUS_ACTIVE if how == 'live' else self.STATUS_VERIFY_RESIZE)
        if how == 'cold':
            self.cloud.os_cmd(['openstack server resize --confirm {}'.format(self.id)], comment=self.name)
            self.wait(cloud=self.cloud, srv_id_name_dic={self.id: self.name}, status=self.STATUS_ACTIVE)
        ans = self.cloud.os_cmd(['openstack server show {} -f json'.format(self.id)], comment=self.name)
        self.dic_from_os = ans[0]
        msg = '{} {} migrated to {}'.format(time.strftime('%b%d %H:%M:%S'), how, self.compute)
        self.console_exe('echo {} >> migration_history'.format(msg))
        return self.console_exe('cat migration_history')

    def snapshot(self):
        self.cloud.od_cmd('nova image-create {0} {0}-snap'.format(self.name))

    def console_exe(self, cmd, timeout=200):
        import paramiko
        import StringIO
        import time
        from lab.with_config import WithConfig

        ch = paramiko.SSHClient()
        ch.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        pkey = paramiko.RSAKey.from_private_key(StringIO.StringIO(WithConfig.PRIVATE_KEY))
        ch.connect(hostname=self.cloud.mediator.ip, username=WithConfig.SQE_USERNAME, pkey=pkey, timeout=10)  # connect to mediator
        shell = ch.invoke_shell(width=1024)
        shell.settimeout(60)

        nc = 'nc {} {}'.format(self.compute, self.srv_serial)
        self.log_debug(nc + cmd)
        started = time.time()

        try:
            a = ''
            while True:
                if shell.recv_ready():
                    a += shell.recv(1024)
                else:
                    if '~]$' in a:
                        break
                    time.sleep(1)
                    if time.time() > started + int(timeout):
                        raise RuntimeError('{}: timeout when waiting for proxy prompt'.format(self))

            shell.send(nc)  # start nc session

            a = ''
            while True:
                if shell.recv_ready():
                    a += shell.recv(1024)
                else:
                    if '~]$' in a:  # we got a prompt from server
                        break
                    if nc in a:
                        shell.send('\n')  # sometimes one needs to say Enter few times to get nc prompt
                    if 'login:' in a:
                        a = ''
                        shell.send(self.srv_username + '\n')
                    if 'Password' in a:
                        shell.send(self.srv_password + '\n')
                    time.sleep(1)
                    if time.time() > started + int(timeout):
                        raise RuntimeError('{}: timeout when waiting for server prompt'.format(self))

            shell.send(cmd + '\n')  # send command

            a = ''
            while True:
                if shell.recv_ready():
                    a += shell.recv(10000)
                else:
                    if '~]$' in a:  # we got a prompt from server after command complete
                        shell.send('exit\n')
                        break
                    time.sleep(1)
                    if time.time() > started + int(timeout):
                        raise RuntimeError('{}: timeout when waiting for {} completion, collected so far {}'.format(self, cmd, a))
            return filter(lambda x: x and '~]$' not in x, a.replace(cmd, '').replace('\r','').split('\n'))
        finally:
            ch.close()
