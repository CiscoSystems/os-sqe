from lab.runners import Runner


class RunnerGetLogs(Runner):

    def sample_config(self):
        return {'cloud': 'string: cloud name',
                'regex': 'string: some regexp to be used in grep, empty means all',
                'minutes': 'int: 10 -> filter out all messages older then 10 minutes ago, 0 means no filter'}

    def __init__(self, config):
        super(RunnerGetLogs, self).__init__(config=config)
        regex = config['regex']
        minutes = int(config['minutes'])

        cmd = 'sudo '
        cmd += 'sed -n "/^$(date +%Y-%m-%d\ %H:%M --date="{min} min ago")/, /^$(date +%Y-%m-%d\ %H:%M)/p" '.format(min=minutes) + '/var/log/{log}/*.log' if minutes else 'cat /var/log/{log}/*.log '
        cmd += '| grep -i ' + regex if regex else ''
        self._command = cmd

    def execute(self, clouds, servers):
        from lab.with_config import open_artifact

        for d in ['neutron', 'nova']:
            for server in servers:
                with open_artifact(name='{0}-{1}-errors.txt'.format(server.name(), d), mode='w') as f:
                    f.write(server.run(command=self._command.format(log=d), warn_only=True))

    @staticmethod
    def store_on_our_server():
        """Store $REPO/*.log and $REPO/artifacts/* on file storage server"""
        from lab import logger
        from lab.server import Server

        destination_dir = '{0}-{1}'.format(logger.JENKINS_TAG, logger.REPO_TAG)
        server = Server(ip='172.29.173.233', username='localadmin', password='ubuntu', lab=None, name='FileStorage')
        server.run(command='mkdir -p /var/www/logs/{0}'.format(destination_dir))
        server.put(local_path='*.log', remote_path='/var/www/logs/' + destination_dir, is_sudo=False)
        server.put(local_path='artifacts/*', remote_path='/var/www/logs/' + destination_dir, is_sudo=False)
