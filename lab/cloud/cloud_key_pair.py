from lab.cloud import CloudObject


class CloudKeyPair(CloudObject):
    def __init__(self, cloud, dic):
        super(CloudKeyPair, self).__init__(cloud=cloud, dic=dic)
        self.fingerprint = dic['fingerprint']
        self.id = self.name

    @staticmethod
    def create(cloud):
        from lab.with_config import WithConfig

        name = CloudObject.UNIQUE_PATTERN_IN_NAME + 'key'
        for kp in cloud.keypairs:
            if kp.name == name:
                return kp
        rem_abs_path = cloud.mediator.r_put_string_to_file_in_dir(str_to_put=WithConfig.PUBLIC_KEY, rem_file_name='sqe_public_key', is_as_sqe=True)
        return CloudKeyPair(cloud=cloud, dic=cloud.os_cmd(['openstack keypair create {} --public-key {} -f json'.format(name, rem_abs_path)])[0])
