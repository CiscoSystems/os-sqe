from lab import WithConfig


class Laboratory(WithConfig.WithConfig):
    def sample_config(self):
        pass

    def __init__(self, config_path):
        from netaddr import IPNetwork
        from lab.Server import Server

        super(Laboratory, self).__init__(config=None)

        cfg = self.read_config_from_file(config_path=config_path)

        with open(WithConfig.KEY_PUBLIC_PATH) as f:
            self.public_key = f.read()

        user_net = IPNetwork(cfg['nets']['user']['cidr'])
        self.gw = user_net[1]

        self.servers = []
        counter = 2
        for x in cfg['nodes']:
            for role, val in x.iteritems():
                for role_counter in xrange(len(val['server-id'])):
                    ip = user_net[-counter]
                    self.servers.append(Server(ip=ip, net=user_net, role='{0}-{1}'.format(role, role_counter)))
                    counter += 1

    def director(self):
        return self.servers[0]

    def all_but_director(self):
        return self.servers[1:]


