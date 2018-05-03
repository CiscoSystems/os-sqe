from lab.cloud import CloudObject


class CloudFlavor(CloudObject):
    STATUS_FLAVOR_CREATING = 'status=FlavorCreating'
    STATUS_FLAVOR_CREATED = 'status=FlavorCreated'

    TYPE_VTS = 'vts'
    TYPE_LARGE = 'm1.large'
    FLAVOR_TYPES = {'vts': {'cmd': 'openstack flavor create {} --vcpu 2 --ram 4096 --disk 20 --public -f json', 'opt': 'openstack flavor set {} --property hw:mem_page_size=large'},
                    'old': {'cmd': 'openstack flavor create {} --vcpu 2 --ram 4096 --disk 20 --public -f json', 'opt': 'openstack flavor set {} --property hw:numa_nodes=1'},
                    'm1.large': {'cmd': 'openstack flavor create {} --vcpu 4 --ram 8192 --disk 80 --public -f json', 'opt': 'openstack flavor set {} --property hw:mem_page_size=large'}
                    }

    def __init__(self, cloud, dic):
        super(CloudFlavor, self).__init__(cloud=cloud, dic=dic)

    @staticmethod
    def create(cloud, flavor_type):

        name = CloudObject.UNIQUE_PATTERN_IN_NAME + flavor_type + '-flavor'
        for flv in cloud.flavors:
            if flv.name == name:
                return flv
        try:
            t = CloudFlavor.FLAVOR_TYPES[flavor_type]
            dic = cloud.os_cmd([t['cmd'].format(name)])[0]
            if 'opt' in t and t['opt']:
                cloud.os_cmd([t['opt'].format(name)])
            return CloudFlavor(cloud=cloud, dic=dic)
        except KeyError:
            raise ValueError('CloudFlavor: wrong flavor "{}" possibles: {}'.format(flavor_type, CloudFlavor.FLAVOR_TYPES.keys()))
