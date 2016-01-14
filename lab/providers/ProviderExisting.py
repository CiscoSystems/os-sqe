from lab.providers import Provider


class ProviderExisting(Provider):
    """Creates servers from a list of existing ips provided in configuration
    """

    def sample_config(self):
        return [{'host': 'srv1.domain.name', 'username': 'username1', 'password': 'password1'}, {'host': '2.2.2.2', 'username': 'user2', 'password': 'password2'}]

    def __init__(self, config):
        from lab.server import Server

        super(ProviderExisting, self).__init__(config=config)
        self.servers = [Server(ip=server['host'], username=server['username'], password=server['password']) for server in config]

    def create_servers(self):
        return self.servers

    def wait_for_servers(self):
        servers = self.create_servers()
        for server in servers:
            server.hostname = server.run(command='hostname')
            server.ip_mac = server.run(command='iface=$(ip -o address | grep {0} | cut -f2 -d " "); ip -o link | grep $iface | cut -f18 -d " "'.format(server.ip))
        return servers
