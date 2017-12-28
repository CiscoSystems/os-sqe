from lab.decorators import section
from lab.cloud import CloudObject


class CloudFlavor(CloudObject):
    TYPE_VTS = 'vts'
    FLAVOR_TYPES = {'vts': {'cmd': 'openstack flavor create {} --vcpu 2 --ram 4096 --disk 20 --public ', 'opt': 'openstack flavor set {} --property hw:mem_page_size=large'},
                    'old': {'cmd': 'openstack flavor create {} --vcpu 2 --ram 4096 --disk 20 --public ', 'opt': 'openstack flavor set {} --property hw:numa_nodes=1'}}

    def __init__(self, cloud, dic):
        super(CloudFlavor, self).__init__(cloud=cloud, dic=dic)

    @staticmethod
    @section('Creating custom flavor')
    def create(cloud, flavor_type):
        from lab.cloud import UNIQUE_PATTERN_IN_NAME

        name = UNIQUE_PATTERN_IN_NAME + flavor_type
        try:
            t = CloudFlavor.FLAVOR_TYPES[flavor_type]
            dic = cloud.os_cmd(t['cmd'].format(name))
            if t['opt']:
                cloud.os_cmd(t['opt'].format(name))
            return CloudFlavor(cloud=cloud, dic=dic)
        except KeyError:
            raise ValueError('CloudFlavor: wrong flavor "{}" possibles: {}'.format(flavor_type, CloudFlavor.FLAVOR_TYPES.keys()))
