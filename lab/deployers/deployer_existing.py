from lab.deployers import Deployer


class DeployerExisting(Deployer):

    def sample_config(self):
        return {'cloud': 'arbitrary name', 'end_point': 'http of cloud end_point',
                'user': 'default user', 'tenant': 'tenant name', 'admin': 'admin username', 'password': 'password for both'}

    def __init__(self, config):
        super(DeployerExisting, self).__init__(config=config)
        self._config = config

    def wait_for_cloud(self, list_of_servers):
        from lab.cloud import Cloud

        cloud = Cloud(cloud=self._config['cloud'], user=self._config['user'], tenant=self._config['tenant'], admin=self._config['admin'],
                      password=self._config['password'], end_point=self._config['end_point'], mediator=list_of_servers[0])
        return cloud.verify_cloud()
