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
        from fabric.api import settings, sudo, put
        from StringIO import StringIO
        from time import sleep

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
                with settings(host_string='{user}@{ip}'.format(user=server.username, ip=server.ip), password=server.password, connection_attempts=50, warn_only=False):
                    self.check_or_install_package(package_name='dibbler-server')
                    put(local_path=StringIO(conf), remote_path='/etc/dibbler/server.conf', use_sudo=True)
                    sudo('dibbler-server start')
                    sudo('ps auxw | grep dibbler | grep -v grep')
                return
        raise ErrorDeployerDibbler('Server {0} expected by config is not provided!'.format(self.hostname))
