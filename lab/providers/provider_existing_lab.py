from lab.providers import Provider


class ProviderExistingLab(Provider):
    """Creates a list of servers from base hardware lab config
    """
    @staticmethod
    def sample_config():
        return {'hardware-lab-config': 'some pod from gitlab'}

    def __init__(self, config):
        from lab.laboratory import Laboratory

        super(ProviderExistingLab, self).__init__()

        self.pod = Laboratory(cfg_or_path=config['hardware-lab-config'])

    def execute(self, servers_and_clouds):
        servers_and_clouds['servers'] = self.pod.nodes.values()
        exceptions = []
        return exceptions
