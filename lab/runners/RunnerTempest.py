from lab.runners import Runner


class RunnerTempest(Runner):

    def sample_config(self):
        return {'hostname': 'host where to run commands', 'tests_regexp': 'regexp'}

    def __init__(self, config):
        self.hostname = config['hostname']
        self.commands = config['commands']

        super(RunnerTempest, self).__init__(config=config)

    def execute(self, clouds, servers):
        
        pass
