from lab.base_lab import LabWorker


class DeployerMercury(LabWorker):

    def sample_config(self):
        return {'mercury_installer_location': 'http://path-to-mercury-release-server-folder', 'type_of_install': 'iso or tarball', 'hardware_lab_config': 'valid lab configuration',
                'vts_images_location': 'http://172.29.173.233/vts/nightly-2016-03-14/', 'rhel_creds_location': 'http://172.29.173.233/redhat/subscriptions/rhel-subscription-chandra.json', 'is_force_redeploy': True, 'is_add_vts_role': False}

    def __init__(self, config, version):
        from lab.deployers.deployer_vts import DeployerVts

        super(DeployerMercury, self).__init__(config=config)

        self._mercury_installer_location = config['mercury_installer_location'].format(version=version)
        self._lab_path = config['hardware_lab_config']
        self._type_of_install = config['type_of_install']
        self._is_force_redeploy = config['is_force_redeploy']
        self._vts_deployer = DeployerVts(config={'vts_images_location': config['vts_images_location'], 'rhel_creds_location': config['rhel_creds_location'], 'is_force_redeploy': self._is_force_redeploy})
        self._is_add_vts_role = config['is_add_vts_role']

    def deploy_cloud(self, list_of_servers):
        from lab.cloud import Cloud
        from lab.cimc import CimcDirector
        from fabric.operations import prompt
        from lab.laboratory import Laboratory

        lab = Laboratory(config_path=self._lab_path)

        try:
            build_node = filter(lambda x: type(x) is CimcDirector, list_of_servers)[0]
        except IndexError:
            build_node = lab.get_director()

        mercury_tag = self._mercury_installer_location.split('/')[-1]
        self.log(message='Deploying {} on {}'.format(mercury_tag, build_node))

        if self._type_of_install == 'iso':
            while True:
                ip, username, password = build_node.get_oob()
                ans = prompt('Run remote mounted ISO installation on http://{} ({}/{}) with RemoteShare={} RemoteFile=buildnode.iso, print FINISH when ready'.format(ip, username, password, self._mercury_installer_location))
                if ans == 'FINISH':
                    break

        lab.r_n9_configure(is_clean_before=True)
        build_node.r_configure_mx_and_nat()

        ans = build_node.exe('ls -d installer*', is_warn_only=True)
        if 'installer-' + mercury_tag in ans:
            installer_dir = ans
            build_node.exe(command='./unbootstrap.sh -y > /dev/null', in_directory=installer_dir, is_warn_only=True, estimated_time=100)
            is_get_tarball = False
        elif 'No such file or directory' in ans:
            installer_dir = 'installer-{}'.format(mercury_tag)
            is_get_tarball = True
        else:
            old_installer_dir = ans
            installer_dir = 'installer-{}'.format(mercury_tag)
            build_node.exe(command='./unbootstrap.sh -y > /dev/null', in_directory=old_installer_dir, is_warn_only=True, estimated_time=100)
            build_node.exe('rm -f openstack-configs', is_warn_only=True)
            build_node.exe('rm -rf {}'.format(old_installer_dir))
            is_get_tarball = True

        if is_get_tarball:
            tar_url = self._mercury_installer_location + '/mercury-installer-internal.tar.gz'
            tar_path = build_node.r_get_remote_file(url=tar_url)
            build_node.exe('tar xzf {}'.format(tar_path))
            build_node.exe('rm -f {}'.format(tar_path))

        ans = build_node.exe('cat /etc/cisco-mercury-release', is_warn_only=True)
        if self._is_force_redeploy or mercury_tag not in ans:
            cfg_body = lab.create_mercury_setup_data_yaml(is_add_vts_role=self._is_add_vts_role)
            build_node.r_put_string_as_file_in_dir(string_to_put=cfg_body, file_name='setup_data.yaml', in_directory=installer_dir + '/openstack-configs')

            build_node.exe("find {} -name '*.pyc' -delete".format(installer_dir))
            build_node.exe('rm -rf /var/log/mercury/*')

            try:
                build_node.exe(command='./runner/runner.py -y -s 7,8 > /dev/null', in_directory=installer_dir, estimated_time=600)  # run steps 1-6 during which we get all control and computes nodes re-loaded
            except:
                build_node.exe('cat /var/log/mercury/installer/*')
                raise RuntimeError('Mercury ./runner/runner.py -y -s 7,8 failed')

            if not self._is_add_vts_role:
                cobbler = lab.get_cobbler()
                cobbler.cobbler_deploy()
            self._vts_deployer.wait_for_cloud(list_of_servers=lab.get_vts_hosts())

            try:
                build_node.exe(command='./runner/runner.py -y -p 7,8 > /dev/null', in_directory=installer_dir, estimated_time=600)  # run steps 7-8
            except:
                build_node.exe('cat /var/log/mercury/installer/*')
                raise RuntimeError('Mercury ./runner/runner.py -y -p 7,8 failed')

            build_node.exe(command='echo {} > /etc/cisco-mercury-release'.format(mercury_tag))

        lab.r_collect_information(regex='ERROR', comment='after mercury runner')

        openrc_body = build_node.exe(command='cat openstack-configs/openrc')
        return Cloud.from_openrc(name=self._lab_path.strip('.yaml'), mediator=build_node, openrc_as_string=openrc_body)

    def execute(self, servers_and_clouds):
        cloud = self.deploy_cloud(list_of_servers=servers_and_clouds['servers'])
        servers_and_clouds['clouds'].append(cloud)
        return cloud.verify_cloud()
