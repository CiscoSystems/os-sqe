import abc
from lab.WithConfig import WithConfig


class Runner(WithConfig):
    @abc.abstractmethod
    def execute(self, clouds, servers):
        pass

    @staticmethod
    def get_artefacts(server):
        configs = ['version:\n{0}'.format(server.run('rpm -qi python-networking-cisco'))]
        for x in ['vlan_ranges', 'ucsm', 'api_workers']:
            cmd = 'sudo grep -r {0} /etc/neutron/* | grep -v \#'.format(x)
            configs.append('\n{0} gives:\n {1}'.format(cmd, server.run(cmd)))

        cmd = 'sudo grep -i ERROR /var/log/neutron/* | grep -i ucsm'
        configs.append('\n{0} gives:\n {1}'.format(cmd, server.run(cmd, warn_only=True)))

        with open('configs-logs.txt', 'w') as f:
            f.write('\n\n'.join(configs))
