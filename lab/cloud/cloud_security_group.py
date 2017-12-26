from lab.decorators import section


class CloudSecurityGroup(object):
    def __init__(self, cloud, dic):
        self.cloud = cloud
        self._dic = dic

    @property
    def id(self):
        return self._dic['ID']

    @property
    def name(self):
        return self._dic['Name']

    @property
    def project_id(self):
        return self._dic['Project']

    @staticmethod
    @section(message='cleanup security groups (estimate 5 secs)')
    def cleanup(cloud, is_all):
        from lab.cloud import UNIQUE_PATTERN_IN_NAME
        from lab.cloud.cloud_project import CloudProject

        special_ids = [p.id for p in CloudProject.list(cloud=cloud) if p.name in ['admin', 'service']]
        lst = filter(lambda y: y.project_id not in special_ids, CloudSecurityGroup.list(cloud=cloud))
        if not is_all:
            lst = filter(lambda s: UNIQUE_PATTERN_IN_NAME in s.name, lst)
        CloudSecurityGroup.delete(sec_groups=lst)

        for sg in filter(lambda y: y.project_id in special_ids, lst):
            rules = cloud.os_cmd(cmd='openstack security group rule list  ' + sg.id)
            cloud.os_cmd(cmd='openstack security group rule delete ' + ' '.join([x['ID'] for x in rules if x['IP Protocol']]))

    @staticmethod
    def list(cloud):
        return [CloudSecurityGroup(cloud=cloud, dic=x) for x in cloud.os_cmd('openstack security group list ')]

    @staticmethod
    def delete(sec_groups):
        if len(sec_groups):
            ids = [p.id for p in sec_groups]
            names = [p.name for p in sec_groups]
            sec_groups[0].cloud.os_cmd('openstack security group delete ' + ' '.join(ids), comment=' '.join(names))
