from lab.providers import Provider


class ProviderExisting(Provider):
    """Creates servers from a list of existing ips provided in configuration
    """

    def sample_config(self):
        return [{'host': 'srv1.domain.name', 'username': 'username1', 'password': 'password1'}, {'host': '2.2.2.2', 'username': 'user2', 'password': 'password2'}]

    def __init__(self, config):
        from lab.server import Server

        super(ProviderExisting, self).__init__(config=config)
        self.servers = [Server(name='director', lab=None, ip=server['host'], username=server['username'], password=server['password']) for server in config]

    def create_servers(self):
        return self.servers

    def wait_for_servers(self):
        servers = self.create_servers()
        for server in servers:
            server.actuate_hostname()
            ip, _, _, _ = server.get_ssh()
            nic_name = server.run(command='ip -o address | grep {0} | cut -f2 -d " "'.format(ip))
            nic_mac = server.run(command='ip -o link | grep {0} | cut -f18 -d " "'.format(nic_name))
            server.add_nic(nic_name=nic_name, mac=nic_mac)
        return servers
