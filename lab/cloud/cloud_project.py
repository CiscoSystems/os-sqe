from lab.decorators import section


class CloudProject(object):
    def __init__(self, cloud, dic):
        self.cloud = cloud
        self._dic = dic

    @property
    def id(self):
        return self._dic['ID']

    @property
    def name(self):
        return self._dic['Name']

    @staticmethod
    @section(message='cleanup projects (estimate 5 secs)')
    def cleanup(cloud, is_all):
        from lab.cloud import UNIQUE_PATTERN_IN_NAME

        lst = filter(lambda p: p.name not in ['admin', 'service'], CloudProject.list(cloud=cloud))
        if not is_all:
            lst = filter(lambda s: UNIQUE_PATTERN_IN_NAME in s['Name'], lst)
        CloudProject.delete(projects=lst)

    @staticmethod
    def delete(projects):
        if len(projects):
            ids = [p.id for p in projects]
            names = [p.name for p in projects]
            projects[0].cloud.os_cmd('openstack project delete ' + ' '.join(ids), comment=' '.join(names))

    @staticmethod
    def list(cloud):
        return [CloudProject(cloud=cloud, dic=x) for x in cloud.os_cmd('openstack project list -f json')]
