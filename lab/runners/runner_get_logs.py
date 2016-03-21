from lab.runners import Runner


class RunnerGetLogs(Runner):

    def sample_config(self):
        return {'cloud': 'cloud name'}

    def __init__(self, config):
        super(RunnerGetLogs, self).__init__(config=config)
        self.list_of_hostname_commands_dicts = config
        self.clouds = []

    def execute(self, clouds, servers):
        for server in servers:
            server.get_file_from_dir()