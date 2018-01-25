class CloudObject(object):
    UNIQUE_PATTERN_IN_NAME = 'sqe-'

    def __init__(self, cloud, dic):
        self.cloud = cloud
        self.id = str(dic.get('id', ''))
        self.name = dic['name']
        self.role = self.__class__.__name__.replace('Cloud', '').lower()
        self.status = dic.get('status', '')

    def __repr__(self):
        return self.name + ' ' + self.status

    @staticmethod
    def create(cloud, dic):
        from lab.cloud.cloud_server import CloudServer
        from lab.cloud.cloud_image import CloudImage
        from lab.cloud.cloud_network import CloudNetwork
        from lab.cloud.cloud_subnet import CloudSubnet
        from lab.cloud.cloud_key_pair import CloudKeyPair
        from lab.cloud.cloud_flavor import CloudFlavor
        from lab.cloud.cloud_port import CloudPort
        from lab.cloud.cloud_project import CloudProject

        if 'disk_format' in dic:
            cloud.images.append(CloudImage(cloud=cloud, dic=dic))
        elif 'hostId' in dic:
            cloud.servers.append(CloudServer(cloud=cloud, dic=dic))
        elif 'fingerprint' in dic:
            cloud.keypairs.append(CloudKeyPair(cloud=cloud, dic=dic))
        elif 'provider:network_type' in dic:
            cloud.nets.append(CloudNetwork(cloud=cloud, dic=dic))
        elif 'subnetpool_id' in dic:
            cloud.subnets.append(CloudSubnet(cloud=cloud, dic=dic))
        elif 'port_security_enabled' in dic:
            cloud.ports.append(CloudPort(cloud=cloud, dic=dic))
        elif 'os-flavor-access:is_public' in dic:
            cloud.flavors.append(CloudFlavor(cloud=cloud, dic=dic))
        elif set(dic.keys()) == {'id', 'name', 'description', 'enabled', 'properties'}:
            cloud.projects.append(CloudProject(cloud=cloud, dic=dic))
        else:
            raise RuntimeError('{}: add this ^^^ dic to this if!')
