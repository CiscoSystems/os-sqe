from lab.deployers import Deployer


class DeployerMercury(Deployer):

    def sample_config(self):
        return {'installer-source': 'http://path-to-mercury-release-server',
                'installer-checksum': 'check-sum',
                'rhel-subsription-creds': 'http://172.29.173.233/redhat/subscriptions/rhel-subscription-chandra.json'}

    def __init__(self, config):
        super(DeployerMercury, self).__init__(config=config)

        self._rhel_creds_source = config['rhel-subsription-creds']

        self._installer_source = config['installer-source']
        self._installer_checksum = config['installer-checksum']

    def deploy_cloud(self, list_of_servers):
        from lab.cloud import Cloud
        from lab.cimc import CimcDirector
        from fabric.operations import prompt

        build_node = filter(lambda x: type(x) is CimcDirector, list_of_servers)[0]
        build_node.register_rhel(self._rhel_creds_source)

        installer_config_template = self.read_config_from_file(config_path='mercury.template', directory='mercury', is_as_string=True)

        lab = build_node.lab()
        _, cimc_username, cimc_password = build_node.get_oob()
        common_ssh_username = build_node.get_ssh()[1]
        dns_ip = build_node.lab().get_dns()[0]

        api_net = lab.get_all_nets()['api']
        api_cidr, api_vlan, api_gw = api_net.cidr, api_net.get_vlan(), api_net[1]
        lb_ip_api = api_net[10]
        lab.make_sure_that_object_is_unique(str(lb_ip_api), 'MERCURY')

        mx_net = lab.get_all_nets()['mx']
        mx_cidr, mx_vlan, mx_gw = mx_net.cidr, mx_net.get_vlan(), mx_net[1]
        lb_ip_mx = mx_net[10]
        lab.make_sure_that_object_is_unique(str(lb_ip_mx), 'MERCURY')

        tenant_net = lab.get_all_nets()['tenant']
        tenant_cidr, tenant_vlan, tenant_gw = tenant_net.cidr, tenant_net.get_vlan(), tenant_net[1]

        bld_ip_mx = build_node.get_nic('mx').get_ip_and_mask()[0]

        vtc = lab.get_node_by_id('vtc1')
        vtc_ip = vtc.get_vip()[0]
        vtc_username = vtc.get_oob()[1]

        controllers_part = '\n     - '.join(map(lambda x: x.hostname(), lab.get_controllers()))
        computes_part = '\n     - '.join(map(lambda x: x.hostname(), lab.get_controllers()))

        servers_part = ''
        for node in lab.get_controllers() + lab.get_controllers():
            ip = node.get_oob()[0]
            ru = node.get_hardware_info()[0]
            servers_part += '   {nm}:\n       cimc_info: {{"cimc_ip" : "{cimc_ip}"}}\n       rack_info: {{"rack_id": "{ru}"}}\n\n'.format(nm=node.hostname(), node_id=node.get_id(), cimc_ip=ip, ru=ru)

        installer_config_body = installer_config_template.format(cimc_username=cimc_username, cimc_password=cimc_password, dns_ip=dns_ip,
                                                                 api_cidr=api_cidr, api_vlan=api_vlan, api_gw=api_gw,
                                                                 mx_cidr=mx_cidr, mx_vlan=mx_vlan, mx_gw=mx_gw, bld_ip_mx=bld_ip_mx,
                                                                 tenant_cidr=tenant_cidr, tenant_vlan=tenant_vlan, tenant_gw=tenant_gw,
                                                                 controllers_part=controllers_part, computes_part=computes_part, servers_part=servers_part,
                                                                 lb_ip_api=lb_ip_api, lb_ip_mx=lb_ip_mx,
                                                                 vtc_vip=vtc_ip, vtc_username=vtc_username, common_ssh_username=common_ssh_username
                                                                 )
        if self._installer_source.endswith('.iso'):
            while True:
                ans = prompt('Run remote mounted ISO installation on {}, print FINISH when ready'.format(build_node.get_oob()))
                if ans == 'FINISH':
                    break
            installer_dir = build_node.run('find . -name installer*')
        else:
            tar_path = build_node.wget_file(url=self._installer_source, to_directory='.', checksum=self._installer_checksum)
            ans = build_node.run('tar xzvf {}'.format(tar_path))
            installer_dir = ans.split('\n')[0].strip('/\r')

            repo_dir = build_node.clone_repo('https://cloud-review.cisco.com/mercury/mercury.git')

            build_node.run('yum install -y $(cat {}/redhat_packages.txt)'.format(installer_dir))
            build_node.run(command='./bootstrap.sh', in_directory=repo_dir + '/internal')

        build_node.run('rm -f /var/log/mercury/*.tar.gz')
        installer_config_path = build_node.put_string_as_file_in_dir(string_to_put=installer_config_body, file_name='mercury-{}.yaml'.format(lab))

        build_node.run(command='./runner/runner.py -y --file {}'.format(installer_config_path), in_directory=installer_dir)

        return Cloud(cloud='mercury', user='demo', admin='admin', tenant='demo', password='????')

    def wait_for_cloud(self, list_of_servers):
        cloud = self.deploy_cloud(list_of_servers=list_of_servers)
        return cloud.verify_cloud()
