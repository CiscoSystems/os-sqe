from lab.server import Server
from lab.decorators import section


class CloudServer(Server):
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_BUILD = 'BUILD'
    STATUS_DELETED = 'DELETED'
    STATUS_SUSPENDED = 'SUSPENDED'

    def __init__(self, cloud, image, dic):
        self.cloud = cloud
        self.server_id = dic['id']
        self.server_name = dic['name']
        self.server_status = dic['status']
        self.libvirt_name = dic['OS-EXT-SRV-ATTR:instance_name']
        self.image = image
        self.compute = filter(lambda x: x.id == dic['OS-EXT-SRV-ATTR:host'], self.cloud.computes)[0]
        self.ips = [x.split('=')[-1] for x in dic['addresses'].split(',')]

        super(CloudServer, self).__init__(ip=self.ips, username=self.image.username, password=self.image.password)

    def __repr__(self):
        return self.server_name or 'No name yet'

    def os_server_reboot(self, hard=False):
        flags = '--hard ' if hard else '--soft '
        self.cloud.os_cmd('openstack server reboot ' + flags + self.server_id, comment=self.server_name)
        self.wait(servers=[self], status=self.STATUS_ACTIVE)

    def os_server_rebuild(self, image):
        self.cloud.os_cmd('openstack server rebuild ' + self.server_id + ' --image ' + image.name, comment=self.server_name)
        self.wait(servers=[self], status=self.STATUS_ACTIVE)

    def os_server_suspend(self):
        self.cloud.os_cmd('openstack server suspend ' + self.server_id, comment=self.server_name)
        self.wait(servers=[self], status=self.STATUS_SUSPENDED)

    def os_server_resume(self):
        self.cloud.os_cmd('openstack server resume ' + self.server_id, comment=self.server_name)
        self.wait(servers=[self], status=self.STATUS_ACTIVE)

    @staticmethod
    def wait(servers, status, timeout=100):
        import time

        if not servers:
            return
        cloud = servers[0].cloud
        required_n_servers = 0 if status == CloudServer.STATUS_DELETED else len(servers)
        start_time = time.time()
        srv_ids = map(lambda x: x.server_id, servers)
        while True:
            our = filter(lambda x: x.server_id in srv_ids, CloudServer.list(cloud=cloud))
            in_error = filter(lambda x: x.server_status == 'ERROR', our)
            in_status = filter(lambda x: x.server_status == status, our) if status != CloudServer.STATUS_DELETED else our
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
        from lab.cloud import UNIQUE_PATTERN_IN_NAME
        from lab.cloud.cloud_port import CloudPort

        servers = []
        for n, comp in [(y, cloud.computes[y % len(cloud.computes)]) for y in range(1, how_many + 1)]:  # distribute servers per compute host in round robin
            ports = CloudPort.create(cloud=cloud, server_number=n, on_nets=on_nets)
            ports_part = ' '.join(map(lambda x: '--nic port-id=' + x.port_id, ports))
            name = UNIQUE_PATTERN_IN_NAME + str(n)
            dic1 = cloud.os_cmd('openstack server create {} --flavor {} --image "{}" --availability-zone nova:{} --security-group default --key-name {} {} -f json'.format(name, flavor.name, image.name, comp.id, key.keypair_name, ports_part))
            dic2 = cloud.os_cmd('openstack server show -f json {} #  {}'.format(dic1['id'], dic1['name']))

            server = CloudServer(cloud=cloud, image=image, dic=dic2)
            servers.append(server)
        CloudServer.wait(servers, status=CloudServer.STATUS_ACTIVE, timeout=timeout)

        return servers

    @staticmethod
    def list(cloud):
        class Tmp:
            def __init__(self, cloud, dic):
                self.cloud = cloud
                self.server_id = dic['ID']
                self.server_name= dic['Name']
                self.server_status = dic['Status']
        return [Tmp(cloud=cloud, dic=x) for x in cloud.os_cmd('openstack server list -f json')]

    @staticmethod
    @section(message='cleanup servers (estimate 10 secs)')
    def cleanup(cloud, is_all):
        from lab.cloud import UNIQUE_PATTERN_IN_NAME

        lst = CloudServer.list(cloud=cloud)
        if not is_all:
            lst = filter(lambda x: UNIQUE_PATTERN_IN_NAME in x.server_name, lst)
        CloudServer.delete(servers=lst)

    @staticmethod
    def delete(servers):
        import time

        if len(servers):
            ids = [s.server_id for s in servers]
            names = [s.server_name for s in servers]
            servers[0].cloud.os_cmd('openstack server delete ' + ' '.join(ids), comment=' '.join(names))
            time.sleep(5)
            CloudServer.wait(servers=servers, status=CloudServer.STATUS_DELETED)
