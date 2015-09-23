import abc
from lab import WithConfig


class Deployer(WithConfig):
    @abc.abstractmethod
    def wait_for_cloud(self, list_of_servers):
        """Make sure that cloud is up and running on the provided list of servers"""
        pass

    @staticmethod
    def is_rpm_or_dpkg():
        from fabric.api import run

        return run('whereis rpm').split(':')[-1]

    @staticmethod
    def check_or_install_package(package_name):
        from fabric.api import sudo, settings

        with settings(warn_only=True):
            if not sudo('whereis {0}'.format(package_name)).split(':')[-1]:
                if Deployer.is_rpm_or_dpkg():
                    sudo('dnf install -y {0}'.format(package_name))
                else:
                    sudo('rm /var/lib/apt/lists/* -vrf')  # This is workaround for ubuntu update fails with Hash Sum mismatch on some packages
                    sudo('apt-get -y -q update && apt-get install -y -q {0}'.format(package_name))

    @staticmethod
    def clone_repo(repo_url):
        from fabric.api import settings, cd, run
        import urlparse

        local_repo_dir = urlparse.urlparse(repo_url).path.split('/')[-1].strip('.git')

        Deployer.check_or_install_package(package_name='git')
        with settings(warn_only=True):
            if run('test -d {0}'.format(local_repo_dir)).failed:
                run('git clone -q {0}'.format(repo_url))
            with cd(local_repo_dir):
                run('git pull -q')
        return local_repo_dir


class CloudStatus:
    ROLE_CONTROLLER = 'controller'
    ROLE_UCSM = 'ucsm'
    ROLE_NETWORK = 'network'
    ROLE_COMPUTE = 'compute'

    def __init__(self):
        self.info = {'controller': [], 'ucsm': [], 'network': [], 'compute': []}
        self.mac_2_ip = {}
        self.hostname_2_ip = {}

    def get(self, role, parameter):
        """
            :param role: controller, network, compute, ucsm
            :param parameter: ip, mac, hostname
            :return: a list of values for given parameter of given role
        """
        return [server.get(parameter) for server in self.info.get(role, [])]

    def get_first(self, role, parameter):
        """
            :param role: controller, network, compute, ucsm
            :param parameter: ip, mac, hostname
            :return: the first value for given parameter of given role
        """
        values = self.get(role=role, parameter=parameter)
        if values:
            return values[0]
        else:
            return 'NoValueFor' + role + parameter

    def add_server(self, config_name, server):
        """ Set all parameters for the given server"""
        if config_name.startswith('aio'):
            role = self.ROLE_CONTROLLER
        else:
            role = None
            for x in self.info.keys():
                if x in config_name:
                    role = x
                    break
            if role is None:
                raise RuntimeError('Failed to deduce cloud role for server {0}'.format(server))

        self.hostname_2_ip[server.hostname] = server.ip
        self.mac_2_ip[server.ip_mac] = server.ip

        _info = {'ip': server.ip, 'mac': server.ip_mac, 'username': server.username, 'hostname': server.hostname, 'password': server.password}
        self.info[role].append(_info)

    def create_open_rc(self):
        """ Creates open_rc for the given cloud"""
        open_rc = """
export OS_USERNAME=admin
export OS_TENANT_NAME=admin
export OS_PASSWORD=admin
export OS_AUTH_URL=http://{ip}:5000/v2.0/
export OS_REGION_NAME=RegionOne
"""
        with open('open_rc', 'w') as f:
            f.write(open_rc.format(ip=self.get_first('controller', 'ip')))

    def log(self):
        from lab.logger import lab_logger

        lab_logger.info('\n\n Report on lab: ')
        for hostname in sorted(self.hostname_2_ip.keys()):
            lab_logger.info(hostname + ': ' + self.hostname_2_ip[hostname])
        lab_logger.info('\n')
        for role in sorted(self.info.keys()):
            lab_logger.info(role + ' ip: ' + ' '.join(self.get(role=role, parameter='ip')))
