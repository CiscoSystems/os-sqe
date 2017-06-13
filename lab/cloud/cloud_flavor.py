from lab.decorators import section


class CloudFlavor(object):
    TYPE_VTS = 'vts'
    FLAVOR_TYPES = {'vts': {'cmd': 'openstack flavor create {} --vcpu 2 --ram 4096 --disk 20 --public -f json', 'opt': 'openstack flavor set {} --property hw:mem_page_size=large'},
                    'old': {'cmd': 'openstack flavor create {} --vcpu 2 --ram 4096 --disk 20 --public -f json', 'opt': 'openstack flavor set {} --property hw:numa_nodes=1'}}

    def __init__(self, cloud, flavor_dic):
        self.cloud = cloud
        self._dic = flavor_dic

    @property
    def id(self):
        return self._dic['id']

    @property
    def name(self):
        return self._dic['name']

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
            return CloudFlavor(cloud=cloud, flavor_dic=dic)
        except KeyError:
            raise ValueError('CloudFlavor: wrong flavor "{}" possibles: {}'.format(flavor_type, CloudFlavor.FLAVOR_TYPES.keys()))

    def delete(self):
        self.cloud.os_cmd(cmd='openstack flavor delete ' + self.id, comment=self.name)

    @staticmethod
    @section(message='cleanup flavors', estimated_time=3)
    def cleanup(cloud, is_all):
        from lab.cloud import UNIQUE_PATTERN_IN_NAME

        lst = cloud.os_cmd('openstack flavor list -f json')
        if not is_all:
            lst = filter(lambda s: UNIQUE_PATTERN_IN_NAME in s['Name'], lst)
        if len(lst):
            ids = [s['ID'] for s in lst]
            names = [s['Name'] for s in lst]
            cloud.os_cmd('openstack flavor delete ' + ' '.join(ids), comment=' '.join(names))
