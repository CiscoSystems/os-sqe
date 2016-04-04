from lab.deployers import Deployer


class DeployerMercury(Deployer):

    def sample_config(self):
        return {'installer-image': 'http://cloud-releases.cisco.com/mercury/releases/mercury-sprints/20160317_1759-mercury-rhel7-osp7/installer.20160317_1759-mercury-rhel7-osp7.tgz',
                'installer-checksum': '79432e5fb8ac9c2c0d5c90f468bcd548d90a07b94d89963eec558ceeb04f54d0',
                'hardware-lab-config': 'hardware-lab'}

    def __init__(self, config):
        from lab.laboratory import Laboratory

        super(DeployerMercury, self).__init__(config=config)

        self._installer_image = config['installer-image']
        self._installer_checksum = config['installer-checksum']
        self._lab = Laboratory(config['hardware-lab-config'])

    def deploy_cloud(self, list_of_servers):
        from lab.cloud import Cloud
        from lab.providers.provider_cobbler import ProviderCobbler

        build_node = self._lab.get_director()
        cobbler_ip, cobbler_username, cobbler_password, _ = self._lab.get_cobbler().get_ssh()

        cobbler_system_name = '{0}-DIRECTOR'.format(self._lab)
        cobbler = ProviderCobbler(config={'host': cobbler_ip, 'user': cobbler_username, 'password': cobbler_password, 'system_password': 'cisco123', 'selector': {'name': cobbler_system_name}, 'force_pxe_boot': True})
        cobbler.wait_for_servers()

        build_node.create_user('jenkins')
        build_node.wget_file(url=self._installer_image, to_directory='.', checksum=self._installer_checksum)

        return Cloud(cloud='mercury', user='demo', admin='admin', tenant='demo', password=self.cloud_password)

    def wait_for_cloud(self, list_of_servers):
        cloud = self.deploy_cloud(list_of_servers=list_of_servers)
        return self.verify_cloud(cloud=cloud)
