from lab.base_lab import LabWorker


class DeployerDevstack(LabWorker):

    def sample_config(self):
        return {'cloud': 'arbitrary name of the cloud', 'user': 'default user name', 'tenant': 'tenant name', 'password': 'password',
                'server_config_pairs': [{'hostname': 'server name ob which to run', 'devstack_config': 'this devstack conf'}]}

    def __init__(self, config):
        import os

        super(DeployerDevstack, self).__init__(config=config)

        self.cloud = config['cloud']
        self.user = config['user']
        self.tenant = config['tenant']
        self.password = config['password']
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
            raise ValueError('No aio or controller provided!')
        self.roles = controllers + others  # this is to ensure that controllers are deployed first
        self.actual_servers = []  # deployment will run on this list

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
            raise ValueError('During populating config, values not found for some placeholders: {0}'.format(config_as_string))
        return config_as_string

    def run_devstack_on_server(self, server, config_as_string):
        repo = server.clone_repo(repo_url='https://git.openstack.org/openstack-dev/devstack.git', server=server)
        server.put(what=config_as_string, name='local.conf', in_directory=repo)
        server.exe(command='./unstack.sh', in_directory=repo, is_warn_only=True)
        server.exe(command='./clean.sh', in_directory=repo, is_warn_only=True)
        server.exe(command='sudo pkill --signal 9 -f python', is_warn_only=True)  # Kill all python processes to avoid errors: Address already in use
        server.exe(command='./stack.sh', in_directory=repo)

    def deploy_cloud(self, servers):
        from lab.cloud import Cloud

        cloud = Cloud(cloud=self.cloud, user=self.user, tenant=self.tenant, admin='admin', password=self.password)
        hostname_vs_server = {server.hostname: server for server in servers}  # {aio: server_obj, ...}
        for role in self.roles:  # [{'hostname': 'aio', 'config_name': 'aio', 'config_as_string': 'blalbl'}, ...]
            if role['hostname'] not in hostname_vs_server.keys():
                raise ValueError('Expected server "{0}" which is not provided'.format(role['hostname']))
            server = hostname_vs_server[role['hostname']]
            cloud.add_server(config_name=role['config_name'], server=server)
            server.config_as_string = role['config_as_string']
            self.actual_servers.append(server)

        for server in self.actual_servers:
            config_after_fill = self.fill_devstack_config(config_as_string=server.config_as_string, cloud_status=cloud)
            self.run_devstack_on_server(server=server, config_as_string=config_after_fill)
        return cloud

    def execute(self, servers_and_clouds):
        cloud = self.deploy_cloud(servers=servers_and_clouds['servers'])
        servers_and_clouds['clouds'].append(cloud)
        return True
