from lab.providers import Provider


class ProviderUCSM(Provider):
    """Creates servers from a list of existing server: service-profile pairs in a given UCSM
    """

    def sample_config(self):
        return {'yaml_path': 'lab description file'}

    def __init__(self, config):
        super(ProviderUCSM, self).__init__(config=config)
        self.yaml_path = config['yaml_path']

    def create_servers(self):
        """They are not actually created, their properties are defined by UCSM"""
        from lab.providers.fi import read_config_ssh

        return read_config_ssh(yaml_path=self.yaml_path, is_director=False).values()

    def wait_for_servers(self):
        """Nothing to do here, since servers might be in off status or bare-metal"""

        return self.create_servers()
