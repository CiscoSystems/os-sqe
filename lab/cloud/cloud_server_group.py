from lab.decorators import section
from lab.cloud import CloudObject


class CloudServerGroup(CloudObject):
    @staticmethod
    @section(message='cleanup server groups (estimate 5 secs)')
    def cleanup(cloud, is_all):
        lst = CloudServerGroup.list(cloud=cloud)
        if not is_all:
            lst = filter(lambda s: CloudObject.UNIQUE_PATTERN_IN_NAME in s['Name'], lst)
        CloudServerGroup.delete(server_groups=lst)

    @staticmethod
    def delete(server_groups):
        if len(server_groups):
            ids = [p.id for p in server_groups]
            names = [p.name for p in server_groups]
            server_groups[0].cloud.os_cmd('nova server-group-delete ' + ' '.join(ids), comment=' '.join(names))

    @staticmethod
    def list(cloud):
        return [CloudServerGroup(cloud=cloud, dic=x) for x in cloud.os_cmd('nova server-group-list')]
