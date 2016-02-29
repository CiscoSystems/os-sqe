from lab.runners import Runner


class ErrorRunnerCLI(Exception):
    pass


class RunnerCLI(Runner):

    def sample_config(self):
        return [{'hostname': 'host where to run commands', 'cloud': 'cloud name', 'commands': ['cmd1', 'cmd2']}]

    def __init__(self, config):
        super(RunnerCLI, self).__init__(config=config)
        self.list_of_hostname_commands_dicts = config
        self.clouds = []

    def execute(self, clouds, servers):
        servers = {server.hostname: server for server in servers}
        clouds = {cloud.cloud: cloud for cloud in clouds}

        for hostname_commands in self.list_of_hostname_commands_dicts:
            hostname = hostname_commands['hostname']
            cloud_name = hostname_commands['cloud']
            commands = hostname_commands['commands']
            if hostname not in servers:
                raise ErrorRunnerCLI('No server with hostname {0} provided'.format(hostname))
            if cloud_name not in clouds:
                raise ErrorRunnerCLI('No cloud with name {0} provided'.format(cloud_name))
            server = servers[hostname]
            cloud = clouds[cloud_name]

            for command in commands:
                if command.startswith('neutron') or command.startswith('nova'):
                    command = '{0} {1}'.format(command, cloud)
                self.run(command=command, server=server)
