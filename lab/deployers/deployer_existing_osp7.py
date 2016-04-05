from lab.deployers import Deployer


class DeployerExistingOSP7(Deployer):

    def sample_config(self):
        return {'cloud': 'arbitrary name', 'hardware-lab-config': 'some of existing hardware lab description'}

    def __init__(self, config):
        super(DeployerExistingOSP7, self).__init__(config=config)
        self.lab_cfg = config['hardware-lab-config']
        self.cloud_name = config['cloud']

    @staticmethod
    def get_deployment_info(director):
        import json
        import lab

        body = director.get_file_from_dir('osp_install_run.json', '/etc')
        lab.OSP7_INFO = json.loads(body)

    def deploy_cloud(self, list_of_servers):
        from lab.cloud import Cloud
        from lab.laboratory import Laboratory

        if list_of_servers:
            director = list_of_servers[0]
        else:
            director = Laboratory(config_path=self.lab_cfg).get_director()

        self.get_deployment_info(director=director)
        rc = director.run(command='cat /home/stack/overcloudrc')
        user = tenant = password = end_point = None
        for line in rc.split('\n'):
            if 'OS_USERNAME' in line:
                user = line.split('=')[-1].strip()
            if 'OS_TENANT_NAME' in line:
                tenant = line.split('=')[-1].strip()
            if 'OS_PASSWORD' in line:
                password = line.split('=')[-1].strip()
            if 'OS_AUTH_URL' in line:
                end_point = line.split('=')[-1].strip()

        return Cloud(cloud=self.cloud_name, user=user, tenant=tenant, admin=tenant, password=password, end_point=end_point, mediator=director)

    def wait_for_cloud(self, list_of_servers):
        cloud = self.deploy_cloud(list_of_servers)
        return cloud.verify_cloud()
