from lab.decorators import section
from lab.cloud import CloudObject


class CloudSecurityGroup(CloudObject):
    STATUS_SECGRP_CREATING = 'status=SecGrpCreating'
    STATUS_SECGRP_CREATED = 'status=SecGrpCreated'

    def __init__(self, cloud, dic):
        super(CloudSecurityGroup, self).__init__(cloud=cloud, dic=dic)

    @staticmethod
    def create(cloud):
        grp_name = CloudSecurityGroup.UNIQUE_PATTERN_IN_NAME + 'grp'
        cloud.os_cmd(cmds=['openstack security group create ' + grp_name,
                           'openstack security group rule create --protocol icmp ' + grp_name,
                           'openstack security group rule create --protocol tcp --dst-port 22:22 ' + grp_name])
        return grp_name
