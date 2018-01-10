from lab.decorators import section
from lab.cloud import CloudObject


class CloudSecurityGroup(CloudObject):
    def __init__(self, cloud, dic):
        super(CloudSecurityGroup, self).__init__(cloud=cloud, dic=dic)

    @staticmethod
    @section(message='cleanup security groups (estimate 5 secs)')
    def cleanup(cloud, is_all):
        from lab.cloud.cloud_project import CloudProject

        special_ids = [p.id for p in CloudProject.list(cloud=cloud) if p.name in ['admin', 'service']]
        lst = filter(lambda y: y.project_id not in special_ids, CloudSecurityGroup.list(cloud=cloud))
        if not is_all:
            lst = filter(lambda s: CloudObject.UNIQUE_PATTERN_IN_NAME in s.name, lst)
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
