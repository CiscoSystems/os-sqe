from lab.deployers import Deployer


class ErrorDeployerOSP7(Exception):
    pass


class DeployerOSP7(Deployer):

    def sample_config(self):
        return {'rh-secret': 'http:// file with RH creds',
                'undercloud_network_cidr': 'cidr',
                'images_url': 'http://1.1.1.1/path/to/dir',
                'director': 'ipv4 of host to match with provided list of servers',
                'cloud_password': 'password to be assigned to cloud'
                }

    def __init__(self, config):
        import os
        from netaddr import IPNetwork
        import requests
        from lab.WithConfig import CONFIG_DIR

        super(DeployerOSP7, self).__init__(config=config)

        rh_creds = requests.get(config['rh-secret']).text
        rh = {x.split('=')[0].strip(): x.split('=')[1].strip() for x in rh_creds.split('\n') if x}
        self.rh_account = rh['rhel_username']
        self.rh_password = rh['rhel_password']
        self.rh_pool_id = rh['rhel_pool']
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

        if 'Subscribed' not in self.director_server.run(command='subscription-manager list'):
            self.director_server.run(command='sudo subscription-manager register --username={0} --password={1}'.format(self.rh_account, self.rh_password))
            self.director_server.run(command='sudo subscription-manager attach --pool={0}'.format(self.rh_pool_id))
            self.director_server.run(command='sudo subscription-manager repos --disable=*')
            self.director_server.run(command='sudo subscription-manager repos ' + ' '.join(repos_to_enable))
            self.director_server.run(command='sudo yum update -y')
            self.director_server.run(command='sudo yum install -y python-rdomanager-oscplugin')

    def __undercloud_config(self):
        iface = self.director_server.run(command="ip -o link | awk '/ee:/ {print $2}'").split('\n')[0]
        undercloud_config = self.undercloud_config_template.format(pxe_iface=iface.strip(':\r'),
                                                                   cidr=str(self.undercloud_network),
                                                                   gw=str(self.undercloud_network[1]),  # gw == local_ip! possible bug or feature?
                                                                   local_ip=str(self.undercloud_network[1]),
                                                                   public_vip=str(self.undercloud_network[3]),
                                                                   admin_vip=str(self.undercloud_network[4]),
                                                                   dhcp_start=str(self.undercloud_network[100]),
                                                                   dhcp_end=str(self.undercloud_network[100 + 50]),
                                                                   discovery_start=str(self.undercloud_network[200]),
                                                                   discovery_end=str(self.undercloud_network[200 + 50]),
                                                                   cloud_password=self.cloud_password,
                                                                   images_dir=self.images_dir
                                                                   )
        self.director_server.put(string_to_put=undercloud_config, file_name='undercloud.conf')
        self.director_server.get(remote_path='undercloud.conf', local_path='undercloud.conf')

    def __deploy_undercloud(self):
        self.__undercloud_config()
        self.director_server.run(command='openstack undercloud install')
        self.__wget_images()
        subnet_id = self.director_server.run(command='source stackrc && neutron subnet-list -c id -f csv').split()[-1].strip('"')
        dns_ip = self.director_server.run(command='grep nameserver /etc/resolv.conf').split()[-1]
        self.director_server.run('source stackrc && neutron subnet-update {id} --dns-nameserver {ip}'.format(id=subnet_id, ip=dns_ip))
        self.director_server.run(command='source stackrc && openstack baremetal import --json ~/overcloud.json')
        self.director_server.run(command='source stackrc && openstack baremetal configure boot')
        self.director_server.run('date')
        self.director_server.run(command='source stackrc && openstack baremetal introspection bulk start')
        self.director_server.run(command='source stackrc && openstack baremetal list')

    def __deploy_overcloud(self):
        if not self.director_server.run(command='source stackrc &&  openstack flavor list | grep baremetal', warn_only=True):
            self.director_server.run(command='source stackrc && openstack flavor create --id auto --ram 4096 --disk 40 --vcpus 1 baremetal')
            self.director_server.run(command='source stackrc && openstack flavor set --property "cpu_arch"="x86_64" --property "capabilities:boot_option"="local" baremetal')
        for x in ['control', 'compute']:
            if not self.director_server.run(command='source stackrc &&  openstack flavor list | grep {0}'.format(x), warn_only=True):
                self.director_server.run(command='source stackrc && openstack flavor create --id auto --ram 128 --disk 500 --vcpus 2 {0}'.format(x))
                self.director_server.run(command='source stackrc && openstack flavor set --property "cpu_arch"="x86_64" --property "capabilities:boot_option"="local" '
                                                 '--property "capabilities:profile"="{0}" {0}'.format(x))

        n_controls = 3

        results = self.director_server.run(command='source stackrc && ironic node-list').split('\n')
        uuids = [line.split()[1] for line in results if line.startswith('+') or line.startswith('| UUID')]
        if len(uuids) < n_controls:
            raise ErrorDeployerOSP7('not enough bare-metal nodes to deploy {0} controllers'.format(n_controls))

        n_computes = len(uuids) - n_controls

        cmd = 'source stackrc && ironic node-update {0} replace properties/capabilities=profile:{1},boot_option:local'
        map(lambda uuid: self.director_server.run(command=cmd.format(uuid, 'control')), uuids[:n_controls])
        map(lambda uuid: self.director_server.run(command=cmd.format(uuid, 'compute')), uuids[n_controls:])

        command = 'source stackrc && openstack overcloud deploy --templates ' \
                  '-e /usr/share/openstack-tripleo-heat-templates/overcloud-resource-registry-puppet.yaml ' \
                  '-e /home/stack/templates/networking-cisco-environment.yaml ' \
                  '--control-flavor control --compute-flavor compute ' \
                  '--control-scale {n_controls} --compute-scale {n_computes} --ceph-storage-scale 0 --block-storage-scale 0 --swift-storage-scale 0 ' \
                  '--neutron-network-type vlan --neutron-disable-tunneling ' \
                  '--neutron-public-interface eth0 --hypervisor-neutron-public-interface eth0 ' \
                  '--neutron-tunnel-type vlan ' \
                  '--neutron-network-vlan-ranges datacentre:10:2500 ' \
                  '--ntp-server 1.ntp.esl.cisco.com'.format(n_controls=n_controls, n_computes=n_computes)

        self.director_server.put(string_to_put=command, file_name='RE-DEPLOY')
        self.director_server.run(command=command)

    def __assign_ips_to_user(self):
        for line in self.director_server.run(command='source stackrc && nova list').split('\n'):
            ip_on_pxe_int = line
            iface_on_user = self.director_server.run("ssh heat-admin@{ip_on_pxe_int} /usr/sbin/ip -o l | awk '/:aa:/ {print $2}'".format(ip_on_pxe_int=ip_on_pxe_int))
            iface_on_user.strip(':')
            self.director_server.run("ssh heat-admin@{ip_on_pxe_int} sudo ip a a 10.23.230.135/27 dev {iface_on_user}".format(ip_on_pxe_int=ip_on_pxe_int))

    def __create_overcloud_config_and_template(self, servers):
        import json
        import os
        from lab.WithConfig import read_config_from_file, CONFIG_DIR

        config = {'nodes': []}
        mac_profiles = []
        ucsm_ip = servers[0].ucsm['ip']
        ucsm_username = servers[0].ucsm['username']
        ucsm_password = servers[0].ucsm['password']

        for server in servers:
            ucsm_profile = server.ucsm['service-profile']
            mac_profiles.append('{0}:{1}'.format(server.ucsm['iface_mac']['eth0'], ucsm_profile))
            pxe_mac = server.ucsm['iface_mac']['pxe-int']

            config['nodes'].append({'mac': [pxe_mac],
                                    'cpu': 2,
                                    'memory': 128000,
                                    'disk': 500,
                                    'arch': 'x86_64',
                                    'pm_type': "pxe_ipmitool",
                                    'pm_user': server.ipmi['username'],
                                    'pm_password': server.ipmi['password'],
                                    'pm_addr': server.ipmi['ip']})
        self.director_server.put(string_to_put=json.dumps(config), file_name='overcloud.json')
        self.director_server.get(remote_path='overcloud.json', local_path='overcloud.json')

        yaml_name = 'networking-cisco-environment.yaml'
        config_tmpl = read_config_from_file(yaml_path=yaml_name, directory='osp7', is_as_string=True)
        config = config_tmpl.format(network_ucsm_ip=ucsm_ip, network_ucsm_username=ucsm_username, network_ucsm_password=ucsm_password,
                                    network_ucsm_host_list=','.join(mac_profiles))
        self.director_server.put(string_to_put=config, file_name=yaml_name, in_directory='templates')

    def deploy_cloud(self, list_of_servers):
        from lab.Cloud import Cloud

        servers = []
        for server in list_of_servers:
            if server.ip == self.director_ip:
                self.director_server = server
            else:
                servers.append(server)

        self.__hostname_and_etc_hosts()
        self.__subscribe_and_install()
        self.__create_user_stack()
        self.__create_overcloud_config_and_template(servers=servers)
        self.__deploy_undercloud()
        self.__deploy_overcloud()
        return Cloud(cloud='osp7', user='demo', admin='admin', tenant='demo', password=self.cloud_password)

    def wait_for_cloud(self, list_of_servers):
        cloud = self.deploy_cloud(list_of_servers=list_of_servers)
        return self.verify_cloud(cloud=cloud, from_server=self.director_server)
