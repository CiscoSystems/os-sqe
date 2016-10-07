from lab.base_lab import LabWorker


class DeployerDibbler(LabWorker):

    def sample_config(self):
        return {'prefix': '2222:2222:2222::/48', 'hostname': 'name'}

    def __init__(self, config):
        super(DeployerDibbler, self).__init__(config=config)
        self.prefix = config['prefix']
        self.hostname = config['hostname']

    def wait_for_cloud(self, list_of_servers):
        conf = '''

iface "{iface}" {
   pd-class {
       pd-pool {prefix}
       pd-length 64
   }
}
'''
        conf = conf.replace('{prefix}', self.prefix)
        conf = conf.replace('{iface}', 'eth1')
        for server in list_of_servers:
            if server.hostname == self.hostname:
                server.check_or_install_packages(package_names='dibbler-server', server=server)
                server.put(what=conf, name='/etc/dibbler/server.conf', server=server)
                server.exe(command='sudo dibbler-server start', server=server)
                server.exe(command='ps auxw | grep dibbler | grep -v grep')
                return
        raise RuntimeError('Server {0} expected by config is not provided!'.format(self.hostname))

    def execute(self, servers_and_clouds):
        return
