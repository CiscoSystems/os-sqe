from lab.decorators import section
from lab.with_log import WithLogMixIn
from lab.cloud import CloudObject


class CloudServer(CloudObject, WithLogMixIn):
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_BUILD = 'BUILD'
    STATUS_DELETED = 'DELETED'
    STATUS_SUSPENDED = 'SUSPENDED'

    def __init__(self, cloud, dic):
        super(CloudServer, self).__init__(cloud=cloud, dic=dic)
        self.srv_libvirt = dic['OS-EXT-SRV-ATTR:instance_name']
        self.image = [x for x in cloud.images if x.img_id == dic['image'].split()[-1].strip('()')][0]
        self.compute = filter(lambda c: c.host_id == dic['OS-EXT-SRV-ATTR:host'], self.cloud.computes)[0]
        self.ips = [x.split('=')[-1] for x in dic['addresses'].split(',')]
        grep = self.compute.host_exe('libvirt virsh dumpxml ' + self.srv_libvirt + ' | grep "source mode="')
        self.srv_serial = grep.split('service=\'')[-1].split('\'')[0]
        self.srv_ip = self.ips[0]
        self.srv_username = self.image.img_username
        self.srv_password = self.image.img_password

    @staticmethod
    def wait(cloud, srv_id_name_dic, status, timeout=100):
        import time

        if not srv_id_name_dic:
            return
        required_n_servers = 0 if status == CloudServer.STATUS_DELETED else len(srv_id_name_dic)
        start_time = time.time()
        while True:
            our = filter(lambda x: x[1] in srv_id_name_dic, cloud.os_cmd(cmd='openstack server list '))
            in_error = filter(lambda x: x[2] == 'ERROR', our)
            in_status = filter(lambda x: x[2] == status, our) if status != CloudServer.STATUS_DELETED else our
            if len(in_status) == required_n_servers:
                return in_status  # all successfully reached the status
            if in_error:
                CloudServer.analyse_servers_problems(servers=in_error)
                raise RuntimeError('These instances failed: {0}'.format(in_error))
            if time.time() > start_time + timeout:
                CloudServer.analyse_servers_problems(servers=our)
                raise RuntimeError('Instances {} are not {} after {} secs'.format(our, status, timeout))
            time.sleep(30)

    @staticmethod
    def analyse_servers_problems(servers):
        for srv in servers:
            srv.compute.exe('pkill -f ' + srv.libvirt_name)
            srv.cloud.pod.r_collect_info(regex=srv.id, comment='fail-of-' + srv.name)

    @staticmethod
    @section(message='create servers (estimate 60 secs)')
    def create(how_many, flavor, image, key, on_nets, timeout, cloud):
        from lab.cloud.cloud_port import CloudPort

        srv_id_name_dic = {}
        for n, comp in [(y, cloud.computes[y % len(cloud.computes)]) for y in range(1, how_many + 1)]:  # distribute servers per compute host in round robin
            ports = CloudPort.create(cloud=cloud, server_number=n, on_nets=on_nets)
            ports_part = ' '.join(map(lambda x: '--nic port-id=' + x.port_id, ports))
            name = CloudObject.UNIQUE_PATTERN_IN_NAME + str(n)
            cmd = 'openstack server create {} --flavor {} --image "{}" --availability-zone nova:{} --security-group default --key-name {} {} '.format(name, flavor.name, image.name, comp.id, key.keypair_name, ports_part)
            dic = cloud.os_cmd([cmd])
            srv_id_name_dic[dic['id']] = dic['name']
        CloudServer.wait(cloud=cloud, srv_id_name_dic=srv_id_name_dic, status=CloudServer.STATUS_ACTIVE, timeout=timeout)
        a = cloud.os_cmd(['for id in {}; do openstack server show $id -f json; done'.format(' '.join(srv_id_name_dic.keys()))])
        return map(lambda x: CloudServer(cloud=cloud, dic=x), a)

    def console_exe(self, cmd, timeout=20):
        import paramiko
        import StringIO
        import time
        from lab.with_config import WithConfig

        ch = paramiko.SSHClient()
        ch.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        pkey = paramiko.RSAKey.from_private_key(StringIO.StringIO(WithConfig.PRIVATE_KEY))
        ch.connect(hostname=self.cloud.mediator.ip, username=self.cloud.mediator.username, pkey=pkey, timeout=10)  # connect to mediator
        shell = ch.invoke_shell(width=1024)
        shell.settimeout(60)

        nc = 'nc {} {}'.format(self.compute, self.srv_serial)

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

            a = ''
            while True:
                if shell.recv_ready():
                    a += shell.recv(1024)
                else:
                    if cmd not in a:
                        shell.send(cmd + '\n')  # send command
                        a = ''
                    if '~]$' in a:  # we got a prompt from server after command complete
                        shell.send('exit\n')
                        break
                    time.sleep(1)
                    if time.time() > started + int(timeout):
                        raise RuntimeError('{}: timeout when waiting for {} completion'.format(self, cmd))
            return a
        finally:
            ch.close()
