from lab.providers import Provider


class ProviderExistingOSP7(Provider):
    """Creates servers from base hardware lab config
    """

    def sample_config(self):
        return {'hardware-lab-config': 'g10.yaml'}

    def __init__(self, config):
        from lab.laboratory import Laboratory

        super(ProviderExistingOSP7, self).__init__(config=config)

        director = Laboratory(config_path=config['hardware-lab-config']).get_director()
        self.servers = [director]

    def create_servers(self):
        return self.servers

    def wait_for_servers(self):
        servers = self.create_servers()
        for server in servers:
            server.hostname = server.run(command='hostname')
            server.ip_mac = server.run(command='iface=$(ip -o address | grep {0} | cut -f2 -d " "); ip -o link | grep $iface | cut -f18 -d " "'.format(server.ip))
        return servers
