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
        from lab.server import Nic
        servers = self.create_servers()
        for server in servers:
            server.actuate_hostname()
            ip, _, _, _ = server.get_ssh()
            nic_name = server.run(command='ip -o address | grep {0} | cut -f2 -d " "'.format(ip))
            nic_mac = server.run(command='ip -o link | grep {0} | cut -f18 -d " "'.format(nic_name))
            server.add_nics([Nic(name=nic_name, mac=nic_mac, node=server)])
        return servers
