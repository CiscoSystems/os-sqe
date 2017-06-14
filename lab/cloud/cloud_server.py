from lab.server import Server
from lab.decorators import section


class CloudServer(Server):

    def __init__(self, cloud, server_dic):
        self.cloud = cloud
        self._dic = server_dic if 'compute' in server_dic else self.cloud.os_server_show(name_or_id=server_dic.get('ID', server_dic.get('id')))
        super(CloudServer, self).__init__(ip=self.ips, username=self.image.username, password=self.image.password)

    def __repr__(self):
        return self.name

    @property
    def compute(self):
        if 'compute' not in self._dic:
            self._dic['compute'] = next(filter(lambda x: x.get_node_id() == self._dic['OS-EXT-SRV-ATTR:host'], self.cloud.computes))
        return self._dic['compute']

    @property
    def ips(self):
        if 'ips' not in self._dic:
            self._dic['ips'] = [x.split('=')[-1] for x in self._dic['addresses'].split(',')]
        return self._dic['ips']

    @property
    def image(self):
        from lab.cloud.cloud_image import CloudImage
        if type(self._dic['image']) is not CloudImage:
            self._dic['image'] = CloudImage(cloud=self.cloud, image_dic={'name': self._dic['image']})
        return self._dic['image']

    @property
    def id(self):
        return self._dic.get('id', self._dic.get('ID', None))

    @property
    def name(self):
        return self._dic.get('name', self._dic.get('Name', None))

    @property
    def status(self):
        return self._dic.get('status', self._dic.get('Status', None))

    def os_server_reboot(self, hard=False):
        flags = '--hard ' if hard else '--soft '
        self.cloud.os_cmd('openstack server reboot ' + flags + self.id, comment=self.name)
        self.wait_servers_ready(cloud=self.cloud, servers=[self], status='ACTIVE')

    def os_server_rebuild(self, image):
        self.cloud.os_cmd('openstack server rebuild ' + self.id + ' --image ' + image.name, comment=self.name)
        self.wait_servers_ready(cloud=self.cloud, servers=[self], status='ACTIVE')

    def os_server_suspend(self):
        self.cloud.os_cmd('openstack server suspend ' + self.id, comment=self.name)
        CloudServer.wait_servers_ready(cloud=self.cloud, servers=[self], status='SUSPENDED')

    def os_server_resume(self):
        self.cloud.os_cmd('openstack server resume ' + self.id, comment=self.name)
        CloudServer.wait_servers_ready(cloud=self.cloud, servers=[self], status='ACTIVE')

    @staticmethod
    def wait_servers_ready(cloud, servers, status, timeout=300):
        import time

        required_n_servers = 0 if status == 'DELETED' else len(servers)
        start_time = time.time()
        srv_ids = map(lambda x: x.id, servers)
        while True:
            our = filter(lambda x: x.id in srv_ids, CloudServer.list(cloud=cloud))
            in_error = filter(lambda x: x.status == 'ERROR', our)
            in_status = filter(lambda x: x.status == status, our) if status != 'DELETED' else our
            if len(in_status) == required_n_servers:
                return in_status  # all successfully reached the status
            if in_error:
                CloudServer.analyse_servers_problems(cloud=cloud, servers=in_error)
                raise RuntimeError('These instances failed: {0}'.format(in_error))
            if time.time() > start_time + timeout:
                CloudServer.analyse_servers_problems(cloud=cloud, servers=our)
                raise RuntimeError('Instances {} are not {} after {} secs'.format(our, status, timeout))
            time.sleep(30)

    @staticmethod
    def analyse_servers_problems(cloud, servers):
        for srv in servers:
            status = cloud.os_server_show(name_or_id=srv.id)
            comp = cloud.pod.get_node_by_id(status['OS-EXT-SRV-ATTR:host'])
            comp.exe('pkill -f {}'.format((status['OS-EXT-SRV-ATTR:instance_name'])))
            cloud.pod.r_collect_information(regex=status['id'], comment='fail-of-' + status['name'])

    @staticmethod
    def create(how_many, flavor_name, image, on_nets, timeout, cloud):
        from lab.cloud import UNIQUE_PATTERN_IN_NAME

        servers = []
        ports = []
        ips = []
        for n, comp in [(y, cloud.computes[y % len(cloud.computes)]) for y in range(1, how_many + 1)]:  # distribute servers per compute host in round robin
            for net in on_nets:
                ip = net.calc_ip(n)
                mac = net.calc_mac(index=n)
                ports.append(cloud.os_port_create(server_number=n, net_name=net.net_name, ip=ip, mac=mac))
                ips.append(ip)
            port_ids = [x['id'] for x in ports]
            server_dic = cloud.os_server_create(srv_name=UNIQUE_PATTERN_IN_NAME + '-' + str(n), flavor_name=flavor_name, image_name=image.name, zone_name=comp.id, port_ids=port_ids)
            server = CloudServer(cloud=cloud, server_dic=server_dic)
            servers.append(server)
        cloud.wait_instances_ready(servers, timeout=timeout)

        return servers

    @staticmethod
    def list(cloud):
        return [CloudServer(cloud=cloud, server_dic=x) for x in cloud.os_cmd('openstack server list -f json')]

    @staticmethod
    @section(message='cleanup servers', estimated_time=10)
    def cleanup(cloud, is_all):
        from lab.cloud import UNIQUE_PATTERN_IN_NAME

        lst = CloudServer.list(cloud=cloud)
        if not is_all:
            lst = filter(lambda x: UNIQUE_PATTERN_IN_NAME in x.name, lst)
        if len(lst):
            ids = [s.id for s in lst]
            names = [s.name for s in lst]
            cloud.os_cmd('openstack server delete ' + ' '.join(ids), comment=' '.join(names))
            CloudServer.wait_servers_ready(cloud=cloud, servers=lst, status='DELETED')
