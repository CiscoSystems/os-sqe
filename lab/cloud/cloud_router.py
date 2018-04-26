from lab.cloud import CloudObject


class CloudRouter(CloudObject):
    STATUS_ROUTER_CREATING = 'status=RouterCreating'
    STATUS_ROUTER_CREATED = 'status=RouterCreated'

    def __init__(self, cloud, dic):
        super(CloudRouter, self).__init__(cloud=cloud, dic=dic)

    @staticmethod
    def create(cloud):
        name = CloudObject.UNIQUE_PATTERN_IN_NAME + 'r'
        cmds = ['openstack router create ' + name + ' -f json']
        for net in cloud.networks:
            for subnet in net.subnets:
                cmds.append('openstack router add subnet ' + name + ' ' + subnet.name)
        ans = cloud.os_cmd(cmds=cmds)
        CloudRouter(cloud=cloud, dic=ans[0])
