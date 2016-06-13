from lab.deployers import Deployer


class DeployerMercury(Deployer):

    def sample_config(self):
        return {'installer-image': 'http://path-to-mercury-release-server',
                'installer-checksum': 'check-sum'}

    def __init__(self, config):
        super(DeployerMercury, self).__init__(config=config)

        self._installer_image = config['installer-image']
        self._installer_checksum = config['installer-checksum']

    def deploy_cloud(self, list_of_servers):
        from lab.cloud import Cloud

        build_node = filter(lambda x: 'director' in x.role(), list_of_servers)
        build_node.create_user('jenkins')
        build_node.wget_file(url=self._installer_image, to_directory='.', checksum=self._installer_checksum)

        installer_config_template = self.read_config_from_file(config_path='mercury.template', directory='mercury', is_as_string=True)
        installer_config_body = installer_config_template
        installer_config_path = build_node.put_string_as_file_in_dir(string_to_put=installer_config_body, file_name='mercury-{}.yaml'.format(self._lab))

        mercury_repo_path = build_node.clone_repo('https://cloud-review.cisco.com/mercury/mercury.git')

        build_node.run('sudo rm -f /var/log/mercury/*.tar.gz')
        build_node.run('cd {}/installer && sudo ./bootstrap.sh'.format(mercury_repo_path))

        build_node.run('cd {}/installer && sudo ./runner/runner.py -y --file {}'.format(mercury_repo_path, installer_config_path))

        return Cloud(cloud='mercury', user='demo', admin='admin', tenant='demo', password=self.cloud_password)

    def wait_for_cloud(self, list_of_servers):
        cloud = self.deploy_cloud(list_of_servers=list_of_servers)
        return cloud.verify_cloud()
