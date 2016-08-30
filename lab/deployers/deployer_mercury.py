from lab.deployers import Deployer


class DeployerMercury(Deployer):

    def sample_config(self):
        return {'installer-source': 'http://path-to-mercury-release-server-folder', 'type-of-install': 'iso or tarball', 'hardware-lab-config': 'valid lab configuration'}

    def __init__(self, config):
        super(DeployerMercury, self).__init__(config=config)

        self._installer_source = config['installer-source']
        self._lab_path = config['hardware-lab-config']
        self._type_of_install = config['type-of-install']

    def deploy_cloud(self, list_of_servers):
        from lab.cloud import Cloud
        from lab.cimc import CimcDirector
        from fabric.operations import prompt
        from lab.laboratory import Laboratory

        try:
            build_node = filter(lambda x: type(x) is CimcDirector, list_of_servers)[0]
        except IndexError:
            l = Laboratory(config_path=self._lab_path)
            build_node = l.get_node_by_id('bld')

        if self._type_of_install == 'iso':
            while True:
                ip, username, password = build_node.get_oob()
                ans = prompt('Run remote mounted ISO installation on http://{} ({}/{}) with RemoteShare={} RemoteFile=buildnode.iso, print FINISH when ready'.format(ip, username, password, self._installer_source))
                if ans == 'FINISH':
                    break
            installer_dir = build_node.run('find . -name installer*')
        else:
            mercury_tag = self._installer_source.split('/')[-1]
            ans = build_node.exe('ls -d installer*')
            if 'installer-' + mercury_tag in ans:
                installer_dir = ans
                build_node.run('test -f setup_data.yaml.orig || cp {}/openstack-configs/setup_data.yaml setup_data.yaml.orig'.format(installer_dir))
            else:
                tar_url = self._installer_source + '/mercury-installer-internal.tar.gz'
                tar_path = build_node.wget_file(url=tar_url)
                ans = build_node.exe('tar xzvf {}'.format(tar_path))
                installer_dir = ans.split('\r\n')[-1].split('/')[1]

                # build_node.run(command='rm -rf mercury')  # https://cisco.jiveon.com/docs/DOC-1503678, https://cisco.jiveon.com/docs/DOC-1502320
                # repo_dir = build_node.clone_repo('https://cloud-review.cisco.com/mercury/mercury.git')
                # build_node.run(command='git checkout 0e865f68e0687f116c9045313c7f6ba9fabb5fd2', in_directory=repo_dir)  # https://cisco.jiveon.com/docs/DOC-1503678, https://cisco.jiveon.com/docs/DOC-1502320
                # build_node.run(command='./bootstrap.sh -T {}'.format(mercury_tag), in_directory=repo_dir + '/internal')
                build_node.exe(command='rm -f openstack-configs')
                build_node.exe(command='./unbootstrap.sh -y', in_directory=installer_dir, is_warn_only=True)
                kernel_version = build_node.run('uname -r')
                if kernel_version != '3.10.0-327.18.2.el7.x86_64':
                    build_node.reboot()

        self.create_setup_yaml(build_node=build_node, installer_dir=installer_dir)
        build_node.exe('rm -rf /var/log/mercury/*')

        build_node.exe(command='./runner/runner.py -y', in_directory=installer_dir)

        return Cloud(cloud='mercury', user='demo', admin='admin', tenant='demo', password='????')

    def create_setup_yaml(self, build_node, installer_dir):
        from lab.with_config import open_artifact

        installer_config_template = self.read_config_from_file(config_path='mercury.template', directory='mercury', is_as_string=True)

        lab = build_node.lab()
        bld_ip_oob, bld_username_oob, bld_password_oob = build_node.get_oob()
        bld_ip_api, bld_username_api, bld_password_api = build_node.get_ssh()
        dns_ip = build_node.lab().get_dns()[0]

        api_net = lab.get_all_nets()['a']
        api_cidr, api_pref_len, api_vlan, api_gw = api_net.get_cidr(), api_net.get_prefix_len(), api_net.get_vlan(), api_net.get_gw()
        lb_ip_api = api_net.get_ip_for_index(10)
        lab.make_sure_that_object_is_unique(str(lb_ip_api), 'MERCURY')

        mx_net = lab.get_all_nets()['mx']
        mx_cidr, mx_pref_len, mx_vlan, mx_gw = mx_net.get_cidr(), mx_net.get_prefix_len(), mx_net.get_vlan(), mx_net.get_gw()
        lb_ip_mx = mx_net.get_ip_for_index(10)
        mx_pool = '{} to {}'.format(mx_net.get_ip_for_index(50), mx_net.get_ip_for_index(90))
        lab.make_sure_that_object_is_unique(str(lb_ip_mx), 'MERCURY')

        tenant_net = lab.get_all_nets()['t']
        tenant_cidr, tenant_vlan, tenant_gw = tenant_net.get_cidr(), tenant_net.get_vlan(), tenant_net.get_gw()
        tenant_pool = '{} to {}'.format(tenant_net.get_ip_for_index(10), tenant_net.get_ip_for_index(250))

        bld_ip_mx = build_node.get_nic('mx').get_ip_and_mask()[0]

        vtc = lab.get_node_by_id('vtc1')
        vtc_mx_ip = vtc.get_vtc_vips()[1]
        _, vtc_username, vtc_password = vtc.get_oob()

        controllers_part = '\n     - '.join(map(lambda x: x.hostname(), lab.get_controllers()))
        computes_part = '\n     - '.join(map(lambda x: x.hostname(), lab.get_computes()))

        servers_part = ''
        for node in lab.get_controllers() + lab.get_computes():
            oob_ip, oob_username, oob_password = node.get_oob()
            ru = node.get_hardware_info()[0]
            servers_part += '   {nm}:\n       cimc_info: {{"cimc_ip" : "{ip}", "cimc_password" : "{p}"}}\n       rack_info: {{"rack_id": "{ru}"}}\n\n'.format(nm=node.hostname(), p=oob_password, ip=oob_ip, ru=ru)

        installer_config_body = installer_config_template.format(common_username_oob=bld_username_oob, common_password_oob=bld_password_api, dns_ip=dns_ip,
                                                                 api_cidr=api_cidr, api_pref_len=api_pref_len, api_vlan=api_vlan, api_gw=api_gw,
                                                                 mx_cidr=mx_cidr, mx_pref_len=mx_pref_len, mx_vlan=mx_vlan, mx_gw=mx_gw, bld_ip_mx=bld_ip_mx, mx_pool=mx_pool,
                                                                 tenant_cidr=tenant_cidr, tenant_vlan=tenant_vlan, tenant_gw=tenant_gw, tenant_pool=tenant_pool,
                                                                 controllers_part=controllers_part, computes_part=computes_part, servers_part=servers_part,
                                                                 lb_ip_api=lb_ip_api, lb_ip_mx=lb_ip_mx,
                                                                 vtc_mx_vip=vtc_mx_ip, vtc_username=vtc_username, vtc_password=vtc_password, common_ssh_username=bld_username_api,
                                                                 bld_ip_oob=bld_ip_oob, bld_username_oob=bld_username_oob, bld_password_oob=bld_password_oob,
                                                                 bld_ip_api=bld_ip_api)

        with open_artifact('setup_data.yaml', 'w') as f:
            f.write(installer_config_body)

        return build_node.put_string_as_file_in_dir(string_to_put=installer_config_body, file_name='setup_data.yaml', in_directory=installer_dir + '/openstack-configs')

    def wait_for_cloud(self, list_of_servers):
        cloud = self.deploy_cloud(list_of_servers=list_of_servers)
        return cloud.verify_cloud()

    def configure_nat(self):
        pass
