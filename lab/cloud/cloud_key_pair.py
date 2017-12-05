from lab.decorators import section


class CloudKeyPair(object):
    def __init__(self, cloud, dic):
        self.cloud = cloud
        self.keypair_name = dic['name']
        self.keypair_fingerprint = dic['fingerprint']

    @staticmethod
    @section('Creating key pair (estimate 5 secs)')
    def create(cloud):
        from lab.with_config import WithConfig
        from lab.cloud import UNIQUE_PATTERN_IN_NAME

        rem_abs_path = cloud.mediator.r_put_string_to_file_in_dir(str_to_put=WithConfig.PUBLIC_KEY, rem_file_name='sqe_public_key', is_as_sqe=True)
        dic = cloud.os_cmd('openstack keypair create {} --public-key {} -f json'.format(UNIQUE_PATTERN_IN_NAME + 'key', rem_abs_path))
        return CloudKeyPair(cloud=cloud, dic=dic)

    @staticmethod
    def delete(keypairs):
        if keypairs:
            cloud = keypairs[0].cloud
            cloud.os_cmd('openstack keypair delete ' + ' '.join([kp.keypair_name for kp in keypairs]))

    @staticmethod
    @section(message='cleanup key pairs (estimate 5 secs)')
    def cleanup(cloud, is_all):
        from lab.cloud import UNIQUE_PATTERN_IN_NAME

        lst = CloudKeyPair.list(cloud=cloud)
        if not is_all:
            lst = filter(lambda s: UNIQUE_PATTERN_IN_NAME in s.keypair_name, lst)
        CloudKeyPair.delete(keypairs=lst)

    @staticmethod
    def list(cloud):
        class Tmp:
            def __init__(self, cloud, dic):
                self.cloud = cloud
                self.keypair_name = dic['Name']

        return [Tmp(cloud=cloud, dic=x) for x in cloud.os_cmd('openstack keypair list -f json')]
