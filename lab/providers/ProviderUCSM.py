from lab.providers import Provider


class ProviderUCSM(Provider):
    """Creates servers from a list of existing server: service-profile pairs in a given UCSM
    """

    def sample_config(self):
        return {'host': 'ucsm.domain.name', 'username': 'username1', 'password': 'password1'}

    def __init__(self, config):
        super(ProviderUCSM, self).__init__(config=config)
        self.ucsm_host = config['host']
        self.ucsm_username = config['username']
        self.ucsm_password = config['password']

    def create_servers(self):
        """They are not actually created, their properties are defined by UCSM"""
        from lab.providers.ucsm import read_config_ssh

        return read_config_ssh(host=self.ucsm_host, username=self.ucsm_username, password=self.ucsm_password)

    def wait_for_servers(self):
        """Nothing to do here, since servers might be in off status or bare-metal"""

        return self.create_servers()
