from lab.deployers import Deployer


class ErrorDeployerDevstack(Exception):
    pass


class DeployerDevstack(Deployer):

    def sample_config(self):
        return {'password': 'password for cloud admin', 'server_config_pairs': [{'hostname': 'server name ob which to run', 'devstack_config': 'this devstack conf'}]}

    def __init__(self, config):
        import os

        super(DeployerDevstack, self).__init__(config=config)
        self.dir_for_devstack_configs = os.path.join(self.CONFIG_DIR, 'devstack')

        with open(os.path.join(self.dir_for_devstack_configs, 'common_section.conf')) as f:
            common_section = f.read()

        common_section = common_section.replace('{password}', config['password'])

        controllers = []
        others = []
        for pair in config['server_config_pairs']:
            hostname = pair['hostname']
            devstack_config = pair['devstack_config']

            config_path = devstack_config if os.path.isfile(devstack_config) else os.path.join(self.dir_for_devstack_configs, devstack_config)
            if not os.path.isfile(config_path):
                avail_configs = '\n'.join([x for x in os.listdir(self.dir_for_devstack_configs) if x != 'common_section.conf'])
                raise IOError('{0} not found. Provide full path or choose one of:\n{1}'.format(config_path, avail_configs))

            with open(os.path.join(self.dir_for_devstack_configs, devstack_config)) as f:
                conf_as_string = common_section + f.read()

            which = controllers if devstack_config.startswith('aio') or devstack_config.startswith('controller') else others
            which.append({'hostname': hostname, 'config_name': devstack_config, 'config_as_string': conf_as_string})

        if not controllers:
            raise ErrorDeployerDevstack('No aio or controller provided!')
        self.roles = controllers + others  # this is to ensure that controllers are deployed first

    def verify_cloud(self):
        pass

    @staticmethod
    def fill_devstack_config(config_as_string, cloud_status):
        if 'controller_ip' in config_as_string:
            config_as_string = config_as_string.replace('{controller_ip}', cloud_status.get_first(role='controller', parameter='ip'))
            config_as_string = config_as_string.replace('{controller_name}', cloud_status.get_first(role='controller', parameter='hostname'))
            config_as_string = config_as_string.replace('{nova_ips}', ','.join(cloud_status.get(role='compute', parameter='ip')))
            config_as_string = config_as_string.replace('{nova_ips}', ','.join(cloud_status.get(role='compute', parameter='ip')))
        if 'ucsm_ip' in config_as_string:
            ucsm_ip = cloud_status.get_first(role='ucsm', parameter='ip')
            ucsm_user = cloud_status.get_first(role='ucsm', parameter='user')
            ucsm_password = cloud_status.get_first(role='ucsm', parameter='password')
            ucsm_host_list = cloud_status.get_first(role='ucsm', parameter='host_list')
            network_node_host = cloud_status.get_first(role='ucsm', parameter='network_node_host')
            config_as_string = config_as_string.replace('{ucsm_ip}', ucsm_ip)
            config_as_string = config_as_string.replace('{ucsm_username}', ucsm_user)
            config_as_string = config_as_string.replace('{ucsm_password}', ucsm_password)
            config_as_string = config_as_string.replace('{ucsm_host_list}', ucsm_host_list)
            config_as_string = config_as_string.replace('{network_node_host}', network_node_host)
        if '{' in config_as_string:
            raise ErrorDeployerDevstack('During populating config, values not found for some placeholders: {0}'.format(config_as_string))
        return config_as_string

    def run_devstack_on_server(self, server, config_as_string):
        from fabric.api import run, put, settings, cd
        from StringIO import StringIO

        with settings(host_string='{user}@{ip}'.format(user=server.username, ip=server.ip), password=server.password, connection_attempts=50, warn_only=False):
            repo = self.clone_repo('https://git.openstack.org/openstack-dev/devstack.git')
            with cd(repo):
                put(local_path=StringIO(config_as_string), remote_path='local.conf')
                with settings(warn_only=True):
                    run('./unstack.sh'.format(repo))
                    run('sudo pkill --signal 9 -f python')  # Kill all python processes to avoid errors: Address already in use
                run('./stack.sh')

    def deploy_cloud(self, servers):
        from lab.deployers import CloudStatus

        status = CloudStatus()
        actual_servers = []  # deployment will run on this list
        hostname_vs_server = {server.hostname: server for server in servers}  # {aio: server_obj, ...}
        for role in self.roles:  # [{'hostname': 'aio', 'config_name': 'aio', 'config_as_string': 'blalbl'}, ...]
            if role['hostname'] not in hostname_vs_server.keys():
                raise ErrorDeployerDevstack('Expected server "{0}" which is not provided'.format(role['hostname']))
            server = hostname_vs_server[role['hostname']]
            status.add_server(config_name=role['config_name'], server=server)
            actual_servers.append((role['config_as_string'], server))

        for config_before_fill, server in actual_servers:
            config_after_fill = self.fill_devstack_config(config_as_string=config_before_fill, cloud_status=status)
            self.run_devstack_on_server(server=server, config_as_string=config_after_fill)

    def wait_for_cloud(self, list_of_servers):
        self.deploy_cloud(servers=list_of_servers)
        self.verify_cloud()
