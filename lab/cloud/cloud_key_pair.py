from lab.decorators import section
from lab.cloud import CloudObject


class CloudKeyPair(CloudObject):
    def __init__(self, cloud, dic):
        super(CloudKeyPair, self).__init__(cloud=cloud, dic=dic)
        self.fingerprint = dic['fingerprint']
        self.id = self.name

    @staticmethod
    @section('Creating key pair (estimate 5 secs)')
    def create(cloud):
        from lab.with_config import WithConfig

        rem_abs_path = cloud.mediator.r_put_string_to_file_in_dir(str_to_put=WithConfig.PUBLIC_KEY, rem_file_name='sqe_public_key', is_as_sqe=True)
        return CloudKeyPair(cloud=cloud, dic=cloud.os_cmd(['openstack keypair create {} --public-key {} -f json'.format(CloudObject.UNIQUE_PATTERN_IN_NAME + 'key', rem_abs_path)])[0])
