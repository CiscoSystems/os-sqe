from lab.decorators import section


class CloudUser(object):
    def __init__(self, cloud, dic):
        self.cloud = cloud
        self._dic = dic

    @property
    def id(self):
        return self._dic['ID']

    @property
    def name(self):
        return self._dic['Name']

    def delete(self):
        self.cloud.os_cmd(cmd='openstack user delete ' + self.id, comment=self.name)

    @staticmethod
    def create(cloud, username, password):
        return CloudUser(cloud=cloud, dic=cloud.os_cmd('openstack user create --password {} {} -f json'.format(password, username)))

    @staticmethod
    @section(message='cleanup users (estimate 5 secs)')
    def cleanup(cloud, is_all):
        from lab.cloud import UNIQUE_PATTERN_IN_NAME

        lst = filter(lambda u: u.name not in ['admin', 'glance', 'neutron', 'cinder', 'nova', 'cloudpulse'], CloudUser.list(cloud=cloud))
        if not is_all:
            lst = filter(lambda s: UNIQUE_PATTERN_IN_NAME in s.name, lst)
        if len(lst):
            ids = [p.id for p in lst]
            names = [p.name for p in lst]
            cloud.os_cmd('openstack user delete ' + ' '.join(ids), comment=' '.join(names))

    @staticmethod
    def list(cloud):
        return [CloudUser(cloud=cloud, dic=x) for x in cloud.os_cmd('openstack user list -f json')]
