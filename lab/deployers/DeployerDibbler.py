from lab.deployers import Deployer


class ErrorDeployerDibbler(Exception):
    pass


class DeployerDibbler(Deployer):

    def sample_config(self):
        return {'prefix': '2222:2222:2222::/48', 'hostname': 'name'}

    def __init__(self, config):
        super(DeployerDibbler, self).__init__(config=config)
        self.prefix = config['prefix']
        self.hostname = config['hostname']

    def verify_cloud(self):
        pass

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
                self.check_or_install_package(package_name='dibbler-server', server=server)
                self.put(what=conf, name='/etc/dibbler/server.conf', server=server)
                self.run(command='sudo dibbler-server start', server=server)
                self.run(command='ps auxw | grep dibbler | grep -v grep')
                return
        raise ErrorDeployerDibbler('Server {0} expected by config is not provided!'.format(self.hostname))
