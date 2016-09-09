from lab.deployers import Deployer


class DeployerMercury(Deployer):

    def sample_config(self):
        return {'mercury_installer_location': 'http://path-to-mercury-release-server-folder', 'type_of_install': 'iso or tarball', 'hardware_lab_config': 'valid lab configuration',
                'vts_images_location': 'http://172.29.173.233/vts/nightly-2016-03-14/', 'rhel_creds_location': 'http://172.29.173.233/redhat/subscriptions/rhel-subscription-chandra.json', 'is_force_redeploy': True}

    def __init__(self, config):
        from lab.deployers.deployer_vts import DeployerVts

        super(DeployerMercury, self).__init__(config=config)

        self._mercury_installer_location = config['mercury_installer_location']
        self._lab_path = config['hardware_lab_config']
        self._type_of_install = config['type_of_install']
        self._vts_deployer = DeployerVts(config={'vts_images_location': config['vts_images_location'], 'rhel_creds_location': config['rhel_creds_location'], 'is_force_redeploy': config['is_force_redeploy']})

    def deploy_cloud(self, list_of_servers):
        from lab.cloud import Cloud
        from lab.cimc import CimcDirector
        from fabric.operations import prompt
        from lab.laboratory import Laboratory

        lab = Laboratory(config_path=self._lab_path)

        try:
            build_node = filter(lambda x: type(x) is CimcDirector, list_of_servers)[0]
        except IndexError:
            build_node = lab.get_node_by_id('bld')

        if self._type_of_install == 'iso':
            while True:
                ip, username, password = build_node.get_oob()
                ans = prompt('Run remote mounted ISO installation on http://{} ({}/{}) with RemoteShare={} RemoteFile=buildnode.iso, print FINISH when ready'.format(ip, username, password, self._mercury_installer_location))
                if ans == 'FINISH':
                    break

        mercury_tag = self._mercury_installer_location.split('/')[-1]
        repo_dir = build_node.clone_repo('https://cloud-review.cisco.com/mercury/mercury.git')
        ans = build_node.exe('ls -d installer*', is_warn_only=True)
        if 'installer-' + mercury_tag in ans:
            installer_dir = ans
        else:
            old_installer_dir = ans
            build_node.exe(command='./unbootstrap.sh -y', in_directory=old_installer_dir, is_warn_only=True)
            build_node.exe('rm -f openstack-configs')
            build_node.exe('rm -rf {}'.format(old_installer_dir))
            tar_url = self._mercury_installer_location + '/mercury-installer-internal.tar.gz'
            tar_path = build_node.wget_file(url=tar_url)
            ans = build_node.exe('tar xzvf {}'.format(tar_path))
            installer_dir = ans.split('\r\n')[-1].split('/')[0]
        self.create_setup_yaml(build_node=build_node, installer_dir=installer_dir)

        special_files = ['/baremetal/baremetal_install.py', '/baremetal/cimcutils.py', 	'/openstack/config_manager.py', '/openstack/hw_validations.py', '/openstack/schema_validation.py', '/openstack/validations.py',
                         '/system_configs/roles_profiles/roles.yaml', '/utils/common.py', '/utils/config_parser.py']

        for name in special_files:
            build_node.exe('/usr/bin/cp {repo_dir}/installer{name} {installer_dir}{name}'.format(repo_dir=repo_dir, installer_dir=installer_dir, name=name))

        build_node.exe("find {} -name '*.pyc' -delete".format(installer_dir))
        build_node.exe('rm -rf /var/log/mercury/*')

        build_node.exe(command='./runner/runner.py -y -s 7,8', in_directory=installer_dir)  # run steps 1-6 during which we get all control and computes nodes re-loaded

        self._vts_deployer.wait_for_cloud(list_of_servers=lab.get_vts_hosts())

        build_node.exe(command='./runner/runner.py -y -p 7,8', in_directory=installer_dir)  # run steps 7-8

        lab.r_collect_information(regex='ERROR', comment='after mercury runner')

        openrc_body = build_node.exe(command='cat openstack-configs/openrc')
        return Cloud.from_openrc(name=self._lab_path.strip('.yaml'), mediator=build_node, openrc_as_string=openrc_body)

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

        controllers_part = '\n     - '.join(map(lambda x: x.get_hostname(), lab.get_controllers()))
        computes_part = '\n     - '.join(map(lambda x: x.get_hostname(), lab.get_computes()))
        vts_hosts_part = '\n     - '.join(map(lambda x: x.get_hostname(), lab.get_vts_hosts()))

        servers_part = ''
        for node in lab.get_controllers() + lab.get_computes() + lab.get_vts_hosts():
            oob_ip, oob_username, oob_password = node.get_oob()
            ru = node.get_hardware_info()[0]
            servers_part += '   {nm}:\n       cimc_info: {{"cimc_ip" : "{ip}", "cimc_password" : "{p}"}}\n       rack_info: {{"rack_id": "{ru}"}}\n\n'.format(nm=node.get_hostname(), p=oob_password, ip=oob_ip, ru=ru)

        installer_config_body = installer_config_template.format(common_username_oob=bld_username_oob, common_password_oob=bld_password_api, dns_ip=dns_ip,
                                                                 api_cidr=api_cidr, api_pref_len=api_pref_len, api_vlan=api_vlan, api_gw=api_gw,
                                                                 mx_cidr=mx_cidr, mx_pref_len=mx_pref_len, mx_vlan=mx_vlan, mx_gw=mx_gw, bld_ip_mx=bld_ip_mx, mx_pool=mx_pool,
                                                                 tenant_cidr=tenant_cidr, tenant_vlan=tenant_vlan, tenant_gw=tenant_gw, tenant_pool=tenant_pool,
                                                                 controllers_part=controllers_part, computes_part=computes_part, vts_hosts_part=vts_hosts_part, servers_part=servers_part,
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
