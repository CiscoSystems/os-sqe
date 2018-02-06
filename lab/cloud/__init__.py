class CloudObject(object):
    UNIQUE_PATTERN_IN_NAME = 'sqe-'

    def __init__(self, cloud, dic):
        self.cloud = cloud
        self.id = str(dic.get('id', ''))
        self.name = dic['name']
        self.role = self.__class__.__name__.replace('Cloud', '').lower()
        self.status = dic.get('status', '').strip('cisco-vts-openstack-identities:')
        if cloud:
            getattr(cloud, self.role + 's').append(self)

    def __repr__(self):
        return self.name + ' ' + self.status

    @staticmethod
    def from_dic(cloud, dic):
        from lab.cloud.cloud_server import CloudServer
        from lab.cloud.cloud_image import CloudImage
        from lab.cloud.cloud_network import CloudNetwork
        from lab.cloud.cloud_subnet import CloudSubnet
        from lab.cloud.cloud_key_pair import CloudKeyPair
        from lab.cloud.cloud_flavor import CloudFlavor
        from lab.cloud.cloud_port import CloudPort
        from lab.cloud.cloud_project import CloudProject

        if 'disk_format' in dic:
            CloudImage(cloud=cloud, dic=dic)
        elif 'hostId' in dic:
            CloudServer(cloud=cloud, dic=dic)
        elif 'fingerprint' in dic:
            CloudKeyPair(cloud=cloud, dic=dic)
        elif 'provider:network_type' in dic:
            CloudNetwork(cloud=cloud, dic=dic)
        elif 'subnetpool_id' in dic:
            CloudSubnet(cloud=cloud, dic=dic)
        elif 'port_security_enabled' in dic:
            CloudPort(cloud=cloud, dic=dic)
        elif 'os-flavor-access:is_public' in dic:
            CloudFlavor(cloud=cloud, dic=dic)
        elif set(dic.keys()) == {'id', 'name', 'description', 'enabled', 'properties'}:
            CloudProject(cloud=cloud, dic=dic)
        else:
            raise RuntimeError('{}: add this ^^^ dic to this if!')
