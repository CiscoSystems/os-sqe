
from lab.Server import Server
from lab.WithConfig import WithConfig


class LabServer(Server, WithConfig):
    def sample_config(self):
        pass

    def __init__(self, ip, username):
        super(LabServer, self).__init__(ip=ip, username=username)
        self.ips_macs = dict()

    @staticmethod
    def director(cfg_path='g10.yaml'):
        from netaddr import IPNetwork

        cfg = LabServer.read_config_from_file(config_path=cfg_path)
        user_net = IPNetwork(cfg['nets']['user']['cidr'])
        ip = user_net[cfg['nodes']['director']['ip-shift'][0]]
        username = cfg['username']
        return LabServer(ip=ip, username=username)

