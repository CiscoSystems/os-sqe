from lab.providers import Provider


class ProviderExistingOSP7(Provider):
    """Creates servers from base hardware lab config
    """

    def sample_config(self):
        return {'hardware-lab-config': 'g10.yaml'}

    def __init__(self, config):
        from netaddr import IPNetwork
        from lab.Server import Server

        super(ProviderExistingOSP7, self).__init__(config=config)

        lab_cfg = self.read_config_from_file(config_path=config['hardware-lab-config'])
        user_net = IPNetwork(lab_cfg['nets']['user']['cidr'])
        self.servers = [Server(ip=str(user_net[lab_cfg['nodes']['director']['ip-shift'][0]]), username='root', password='cisco123')]

    def create_servers(self):
        return self.servers

    def wait_for_servers(self):
        servers = self.create_servers()
        for server in servers:
            server.hostname = self.run(command='hostname', server=server)
            server.ip_mac = self.run(command='iface=$(ip -o address | grep {0} | cut -f2 -d " "); ip -o link | grep $iface | cut -f18 -d " "'.format(server.ip), server=server)
        return servers
