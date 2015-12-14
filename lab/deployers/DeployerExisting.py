from lab.deployers import Deployer


class ErrorDeployerExisting(Exception):
    pass


class DeployerExisting(Deployer):

    def sample_config(self):
        return {'cloud': 'arbitrary name', 'end_point': 'http of cloud end_point',
                'user': 'default user', 'tenant': 'tenant name', 'admin': 'admin username', 'password': 'password for both'}

    def __init__(self, config):
        from lab.Cloud import Cloud

        super(DeployerExisting, self).__init__(config=config)
        self.cloud_end_point_ip = config['end_point']
        self.cloud = Cloud(cloud=config['cloud'], user=config['user'], tenant=config['tenant'], admin=config['admin'], password=config['password'], end_point=config['end-point'])

    def wait_for_cloud(self, list_of_servers):
        return self.verify_cloud(cloud=self.cloud, from_server=list_of_servers[0])
