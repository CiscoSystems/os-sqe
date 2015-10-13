from lab.deployers import Deployer


class ErrorDeployerOSP7(Exception):
    pass


class DeployerOSP7(Deployer):

    def sample_config(self):
        return {'rdo_account': 'email as username on RDO',
                'rdo_password': 'password on RDO',
                'rdo_pool_id': 'pool ID on RDO',
                'undercloud_network_cidr': 'cidr',
                'images_url': 'http://1.1.1.1/path/to/dir',
                'director': 'ipv4 of host to match with provided list of servers',
                'cloud_password': 'password to be assigned to cloud'
                }

    def __init__(self, config):
        import os
        from netaddr import IPNetwork
        from lab.WithConfig import CONFIG_DIR

        super(DeployerOSP7, self).__init__(config=config)
        self.rdo_account = config['rdo_account']
        self.rdo_password = config['rdo_password']
        self.rdo_pool_id = config['rdo_pool_id']
        self.images_url = config['images_url']
        self.director_ip = config['director']
        self.cloud_password = config['cloud_password']
        self.undercloud_network = IPNetwork(config['undercloud_network_cidr'])
        self.director_server = None
        self.images_dir = 'images'

        with open(os.path.join(CONFIG_DIR, 'osp7', 'undercloud_conf.template')) as f:
            self.undercloud_config_template = f.read()

    def __wget_images(self):
        images = {'discovery-ramdisk-7.0.0-32.tar': 'd1ddf17d68c36d8dd6ff4083018bd530a79baa29008db8cd4eb19a09e038d0df',
                  'deploy-ramdisk-ironic-7.0.0-32.tar': 'ddc2e62c974f3936692c337ff0df345ae43c6875748a60ca2a95e17473bb45e9',
                  'overcloud-full-7.0.0-32.tar': '33c08823e459f19df49b8a997637df6029337113fd717e4bc9119965c40dee94'
                  }

        self.run(command='mkdir -p images', server=self.director_server)
        for file_name, checksum in images.iteritems():
            self.wget_file(url=self.images_url + '/' + file_name, to_directory=self.images_dir, checksum=checksum, server=self.director_server)
            self.run(command='tar -xf {}'.format(file_name), in_directory=self.images_dir, server=self.director_server)
        self.run(command='source ../stackrc && openstack overcloud image upload', in_directory=self.images_dir, server=self.director_server)

    def __create_user_stack(self):
        new_username = 'stack'

        if not self.run(command='grep {0} /etc/passwd'.format(new_username), server=self.director_server, warn_only=True):
            encrypted_password = self.run(command='openssl passwd -crypt {0}'.format(self.director_server.password), server=self.director_server)
            self.run(command='sudo adduser -p {0} {1}'.format(encrypted_password, new_username), server=self.director_server)
            self.run(command='sudo echo "{0} ALL=(root) NOPASSWD:ALL" | tee -a /etc/sudoers.d/{0}'.format(new_username), server=self.director_server)
            self.run(command='sudo chmod 0440 /etc/sudoers.d/{0}'.format(new_username), server=self.director_server)

        self.director_server.username = new_username

    def deploy_cloud(self):
        from lab.Cloud import Cloud

        self.__hostname_and_etc_hosts()
        self.__subscribe_and_install()
        self.__create_user_stack()
        self.__deploy_undercloud()
        self.__deploy_overcloud()
        return Cloud(cloud='osp7', user='demo', admin='admin', tenant='demo', password=self.cloud_password)

    def __hostname_and_etc_hosts(self):
        hostname = self.run(command='hostname', server=self.director_server)
        if not self.run(command='grep {0} /etc/hosts'.format(hostname), server=self.director_server, warn_only=True):
            self.run(command='sudo echo 127.0.0.1\t{0} >> /etc/hosts'.format(hostname), server=self.director_server)

    def __subscribe_and_install(self):
        repos_to_enable = ['--enable=rhel-7-server-rpms',
                           '--enable=rhel-7-server-optional-rpms',
                           '--enable=rhel-7-server-extras-rpms',
                           '--enable=rhel-7-server-openstack-7.0-rpms',
                           '--enable=rhel-7-server-openstack-7.0-director-rpms']

        self.run(command='sudo subscription-manager register --username={0} --password={1}'.format(self.rdo_account, self.rdo_password), server=self.director_server)
        self.run(command='sudo subscription-manager attach --pool={0}'.format(self.rdo_pool_id), server=self.director_server)
        self.run(command='sudo subscription-manager repos --disable=*', server=self.director_server)
        self.run(command='sudo subscription-manager repos ' + ' '.join(repos_to_enable), server=self.director_server)
        self.run(command='sudo yum update -y', server=self.director_server)
        self.run(command='sudo yum install -y python-rdomanager-oscplugin', server=self.director_server)

    def __undercloud_config(self):
        iface = self.run(command="ip -o link | awk '/ee:/ {print $2}'", server=self.director_server)
        n_overcloud_nodes = 5
        undercloud_config = self.undercloud_config_template.format(pxe_iface=iface.strip(':'),
                                                                   cidr=str(self.undercloud_network),
                                                                   gw=str(self.undercloud_network[1]),
                                                                   local_ip=str(self.undercloud_network[2]),
                                                                   public_vip=str(self.undercloud_network[3]),
                                                                   admin_vip=str(self.undercloud_network[4]),
                                                                   dhcp_start=str(self.undercloud_network[100]),
                                                                   dhcp_end=str(self.undercloud_network[100 + n_overcloud_nodes]),
                                                                   discovery_start=str(self.undercloud_network[200]),
                                                                   discovery_end=str(self.undercloud_network[200 + n_overcloud_nodes]),
                                                                   cloud_password=self.cloud_password,
                                                                   images_dir=self.images_dir
                                                                   )
        self.put(what=undercloud_config, name='undercloud.conf', server=self.director_server)

    def __deploy_undercloud(self):
        self.__undercloud_config()
        self.run(command='openstack undercloud install', server=self.director_server)
        self.__wget_images()
        subnet_id = self.run(command='source stackrc && neutron subnet-list -c id -f csv', server=self.director_server).split()[-1].strip('"')
        dns_ip = self.run(command='grep nameserver /etc/resolv.conf', server=self.director_server).split()[-1]
        self.run('source stackrc && neutron subnet-update {id} --dns-nameserver {ip}'.format(id=subnet_id, ip=dns_ip), server=self.director_server)

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
            config['nodes'].append({'mac': [server.pxe_mac],
                                    'cpu': 2,
                                    'memory': 128,
                                    'disk': 500,
                                    'arch': 'x86_64',
                                    'pm_type': "pxe_ipmitool",
                                    'pm_user': server.ipmi['username'],
                                    'pm_password': server.ipmi['password'],
                                    'pm_addr': server.ipmi['ip']})
        self.__overcloud_config = StringIO(json.dumps(config))

    def wait_for_cloud(self, list_of_servers):
        servers = []
        for server in list_of_servers:
            if server.ip == self.director_ip:
                self.director_server = server
            else:
                servers.append(server)
        self.__create_overcloud_config(servers=servers)
        cloud = self.deploy_cloud()
        return self.verify_cloud(cloud=cloud, from_server=self.director_server)
