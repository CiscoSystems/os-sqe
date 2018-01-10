from lab.decorators import section
from lab.cloud import CloudObject


class CloudUser(CloudObject):
    @section('Create user')
    @staticmethod
    def create(cloud, username, password):
        return CloudUser(cloud=cloud, dic=cloud.os_cmd(['openstack user create --password {} {} -f json'.format(password, username)]))
