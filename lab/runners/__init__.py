import abc
from lab.with_config import WithConfig


class Runner(WithConfig):
    @abc.abstractmethod
    def execute(self, clouds, servers):
        pass

    @staticmethod
    def get_artifacts(server):
        configs = ['version:\n{0}'.format(server.run('rpm -qi python-networking-cisco'))]
        for x in ['vlan_ranges', 'ucsm', 'api_workers']:
            cmd = 'sudo grep -r {0} /etc/neutron/* | grep -v \#'.format(x)
            configs.append('\n{0} gives:\n {1}'.format(cmd, server.run(cmd)))

        cmd = 'sudo grep -i ERROR /var/log/neutron/* | grep -i ucsm'
        configs.append('\n{0} gives:\n {1}'.format(cmd, server.run(cmd, warn_only=True)))

        with open('configs-logs.txt', 'w') as f:
            f.write('\n\n'.join(configs))

    @staticmethod
    def store_artifacts():
        """Store $REPO/*.log and $REPO/artifacts/* on file storage server"""
        import lab
        from lab.server import Server

        destination_dir = '{0}-{1}'.format(lab.JENKINS_TAG, lab.REPO_TAG)
        server = Server(ip='172.29.173.233', username='localadmin', password='ubuntu')
        server.run(command='mkdir -p /var/www/logs/{0}'.format(destination_dir))
        server.put(local_path='*.log', remote_path='/var/www/logs/' + destination_dir, is_sudo=False)
        server.put(local_path='artifacts/*', remote_path='/var/www/logs/' + destination_dir, is_sudo=False)
