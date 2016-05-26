from lab.deployers import Deployer


class DeployerExisting(Deployer):

    def sample_config(self):
        return {'cloud': 'arbitrary name', 'hardware-lab-config': 'yaml which describes the lab'}

    def __init__(self, config):
        super(DeployerExisting, self).__init__(config=config)
        self._lab_cfg = config['hardware-lab-config']
        self._cloud_name = config['cloud']

    def deploy_cloud(self, list_of_servers):
        from lab.laboratory import Laboratory
        from lab.cloud import Cloud

        if not list_of_servers:
            lab = Laboratory(config_path=self._lab_cfg)
            list_of_servers.append(lab.get_director())
            list_of_servers.extend(lab.get_controllers())
            list_of_servers.extend(lab.get_computes())

        director = list_of_servers[0]
        overcloud_openrc = director.run(command='cat keystonerc_admin')
        for host in list_of_servers:
            host.actuate_hostname()
        return Cloud.from_openrc(name=self._cloud_name, mediator=director, openrc_as_string=overcloud_openrc)

    def wait_for_cloud(self, list_of_servers):
        cloud = self.deploy_cloud(list_of_servers)
        return cloud.verify_cloud()
