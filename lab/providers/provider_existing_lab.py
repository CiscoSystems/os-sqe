from lab.providers import Provider


class ProviderExistingLab(Provider):
    """Creates servers from base hardware lab config
    """

    def sample_config(self):
        return {'hardware-lab-config': 'g10.yaml'}

    def __init__(self, config):
        from lab.laboratory import Laboratory

        super(ProviderExistingLab, self).__init__(config=config)

        self._lab = Laboratory(config_path=config['hardware-lab-config']).get_director()

    def create_servers(self):
        return self._lab.get_nodes_by_class()

    def wait_for_servers(self):

        servers = self.create_servers()
        for server in servers:
            server.actuate_hostname()
        return servers
