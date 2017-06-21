from lab.decorators import section


class CloudKeyPair(object):
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
    @section('Creating key pair (estimate 10 secs)')
    def create(cloud):
        from lab import with_config
        from lab.cloud import UNIQUE_PATTERN_IN_NAME

        with open(with_config.KEY_PUBLIC_PATH) as f:
            public_path = cloud.mediator.r_put_string_as_file_in_dir(string_to_put=f.read(), file_name='sqe_public_key')

        cloud.os_cmd('openstack keypair create {} --public-key {}'.format(UNIQUE_PATTERN_IN_NAME + 'key', public_path))

    @staticmethod
    def delete(keypairs):
        if keypairs:
            cloud = keypairs[0].cloud
            cloud.os_cmd('openstack keypair delete ' + ' '.join([kp.name for kp in keypairs]))

    @staticmethod
    @section(message='cleanup key pairs (estimate 5 secs)')
    def cleanup(cloud, is_all):
        from lab.cloud import UNIQUE_PATTERN_IN_NAME

        lst = CloudKeyPair.list(cloud=cloud)
        if not is_all:
            lst = filter(lambda s: UNIQUE_PATTERN_IN_NAME in s['Name'], lst)
        CloudKeyPair.delete(keypairs=lst)

    @staticmethod
    def list(cloud):
        return [CloudKeyPair(cloud=cloud, dic=x) for x in cloud.os_cmd('openstack keypair list -f json')]
