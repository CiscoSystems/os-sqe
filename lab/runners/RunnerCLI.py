from lab.runners import Runner


class ErrorRunnerCLI(Exception):
    pass


class RunnerCLI(Runner):

    def sample_config(self):
        return {'hostname': 'host where to run commands', 'commands': ['cmd1', 'cmd2']}

    def __init__(self, config):
        self.hostname = config['hostname']
        self.commands = config['commands']

        super(RunnerCLI, self).__init__(config=config)

    def run(self, servers):
        from fabric.api import settings, run

        server = [x for x in servers if x.hostname==self.hostname]

        if len(server) == 0:
            raise ErrorRunnerCLI('No server with hostname {0} provided'.format(self.hostname))

        server = server[0]
        with settings(host_string='{user}@{ip}'.format(user=server.username, ip=server.ip), password=server.password, connection_attempts=50, warn_only=False):
            for command in self.commands:
                run(command)
