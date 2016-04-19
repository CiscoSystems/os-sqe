from lab.runners import Runner


class RunnerGetLogs(Runner):

    def sample_config(self):
        return {'cloud': 'cloud name', 'regex': 'some regexp to be used in grep'}

    def __init__(self, config):
        super(RunnerGetLogs, self).__init__(config=config)
        self._cloud_name = config['cloud']
        self._regex = config['regex']

    def execute(self, clouds, servers):
        from lab.with_config import open_artifact

        for d in ['neutron', 'nova']:
            for server in servers:
                with open_artifact(name='{0}-{1}-errors.txt'.format(server.name(), d), mode='w') as f:
                    f.write(server.run('sudo grep -i {regex} /var/log/{d}/*.log'.format(regexp=self._regex, d=d)))

    @staticmethod
    def store_on_our_server():
        """Store $REPO/*.log and $REPO/artifacts/* on file storage server"""
        import lab
        from lab.server import Server

        destination_dir = '{0}-{1}'.format(lab.JENKINS_TAG, lab.REPO_TAG)
        server = Server(ip='172.29.173.233', username='localadmin', password='ubuntu')
        server.run(command='mkdir -p /var/www/logs/{0}'.format(destination_dir))
        server.put(local_path='*.log', remote_path='/var/www/logs/' + destination_dir, is_sudo=False)
        server.put(local_path='artifacts/*', remote_path='/var/www/logs/' + destination_dir, is_sudo=False)
