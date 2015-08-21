from lab.deployers import Deployer


class ErrorDeployerOSP7(Exception):
    pass


class DeployerOSP7(Deployer):

    def sample_config(self):
        return {'rdo_account': 'email as username on RDO',
                'rdo_password': 'password on RDO',
                'rdo_pool_id': 'pool ID on RDO',
                'undercloud_config_file': 'valid config file',
                'images_url': 'http://1.1.1.1/path/to/dir',
                'director': 'ipv4 of host to match with provided list of servers'
                }

    def __init__(self, config):
        import os
        from lab import CONFIG_DIR

        super(DeployerOSP7, self).__init__(config=config)
        self.rdo_account = config['rdo_account']
        self.rdo_password = config['rdo_password']
        self.rdo_pool_id = config['rdo_pool_id']
        self.undercloud_config = os.path.abspath(os.path.join(CONFIG_DIR, 'osp7', config['undercloud_config_file']))
        self.images_url = config['images_url']
        self.director_ip = config['director']
        self.director_username = 'None'
        self.director_password = 'None'

    def __wget_images(self):
        from fabric.api import run, cd

        images = {'discovery-ramdisk-7.0.0-32.tar': 'd1ddf17d68c36d8dd6ff4083018bd530a79baa29008db8cd4eb19a09e038d0df',
                  'deploy-ramdisk-ironic-7.0.0-32.tar': 'ddc2e62c974f3936692c337ff0df345ae43c6875748a60ca2a95e17473bb45e9',
                  'overcloud-full-7.0.0-32.tar': '33c08823e459f19df49b8a997637df6029337113fd717e4bc9119965c40dee94'
                  }

        run('mkdir -p images')
        with cd('images'):
            for file_name, checksum in images.iteritems():
                run('test -e  {loc} || wget -nv {url}/{loc} -O {loc}'.format(loc=file_name, url=self.images_url))
                reculculated_checksum = run('sha256sum {loc}'.format(loc=file_name)).split()[0]
                if reculculated_checksum != checksum:
                    run('rm {}'.format(file_name))
                    raise ErrorDeployerOSP7('I deleted image {} since it is broken (checksum is not matched). Re-run the script'.format(file_name))
                run('tar -xf {}'.format(file_name))
            run('source ../stackrc && openstack overcloud image upload')

    def deploy_cloud(self):
        from fabric.api import settings

        with settings(host_string='{user}@{ip}'.format(user=self.director_username, ip=self.director_ip), password=self.director_password, connection_attempts=50, warn_only=False):
            self.__subscribe_and_install()
            self.__deploy_undercloud()
            self.__deploy_overcloud()

    def __subscribe_and_install(self):
        from fabric.api import sudo

        repos_to_enable = ['--enable=rhel-7-server-rpms',
                           '--enable=rhel-7-server-optional-rpms',
                           '--enable=rhel-7-server-extras-rpms',
                           '--enable=rhel-7-server-openstack-7.0-rpms',
                           '--enable=rhel-7-server-openstack-7.0-director-rpms']

        sudo('subscription-manager register --username={0} --password={1}'.format(self.rdo_account, self.rdo_password))
        sudo('subscription-manager attach --pool={0}'.format(self.rdo_pool_id))
        sudo('subscription-manager repos --disable=*')
        sudo('subscription-manager repos ' + ' '.join(repos_to_enable))
        sudo('yum update -y')
        sudo('yum install -y python-rdomanager-oscplugin')

    def __deploy_undercloud(self):
        from fabric.api import put, sudo

        put(local_path=self.undercloud_config, remote_path='/root/undercloud.conf')
        sudo('openstack undercloud install')
        self.__wget_images()
        subnet_id = sudo('source stackrc && neutron subnet-list -c id -f csv').split()[-1].strip('"')
        dns_ip = sudo('grep nameserver /etc/resolv.conf').split()[-1]
        sudo('source stackrc && neutron subnet-update {id} --dns-nameserver {ip}'.format(id=subnet_id, ip=dns_ip))

    def __deploy_overcloud(self):
        from fabric.api import put, sudo

        put(local_path=self.__overcloud_config, remote_path='overcloud.json')
        sudo('source stackrc && openstack baremetal import --json ~/overcloud.json')
        sudo('source stackrc && openstack baremetal configure boot')
        sudo('source stackrc && openstack baremetal introspection bulk start')

    def __create_overcloud_config(self, servers):
        from StringIO import StringIO
        import json

        config = {'nodes': []}
        for server in servers:
            config['nodes'].append({'mac': [server.nics['eth1']],
                                    'cpu': server.n_cores,
                                    'memory': server.mem_size_gb,
                                    'disk': server.disk_size_gb,
                                    'arch': server.arch,
                                    'pm_type': "pxe_ipmitool",
                                    'pm_user': server.ipmi['username'],
                                    'pm_password': server.ipmi['password'],
                                    'pm_addr': server.ipmi['ip']})
        self.__overcloud_config = StringIO(json.dumps(config))

    def verify_cloud(self):
        pass

    def wait_for_cloud(self, list_of_servers):
        servers = []
        for server in list_of_servers:
            if server['host'] == self.director_ip:
                self.director_username = server['username']
                self.director_password = server['password']
            else:
                servers.append(server)
        self.__create_overcloud_config(servers=servers)
        self.deploy_cloud()
        self.verify_cloud()
