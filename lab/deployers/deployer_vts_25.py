from lab.base_lab import LabWorker


class DeployerVts25(LabWorker):

    @staticmethod
    def sample_config():
        return {'vts_images_url': 'http://wwwin-nfv-orch.cisco.com/mercury/VTC-latest/', 'rhel_creds_location': 'http://172.29.173.233/redhat/subscriptions/rhel-subscription-chandra.json', 'is_force_redeploy': True}

    def __init__(self, config):
        import re
        import requests

        super(DeployerVts25, self).__init__()

        self.is_force_redeploy = True

        self.libvirt_domain_tmpl = self.read_config_from_file(config_path='domain_template.txt', directory='libvirt', is_as_string=True)
        self.disk_part_tmpl = self.read_config_from_file(config_path='disk-part-of-libvirt-domain.template', directory='vts', is_as_string=True)

        self.vts_service_dir = '/var'
        self.vtc_image_abs_path = self.vts_service_dir + '/vtc.qcow2'
        self.vtsr_image_abs_path = self.vts_service_dir + '/vtsr.qcow2'

        self.vts_images_url = config['vts-images-url']
        ans = requests.get(self.vts_images_url + '/checksum')
        self.vtc_image_checksum, self.vtsr_image_checksum  = re.findall(r'^(.{32})\s+vt', ans.text, re.MULTILINE)
        self.vtc_image_url= self.vts_images_url + '/vtc.qcow2'
        self.vtsr_image_url = self.vts_images_url + '/vtsr.qcow2'

    def download_vts_images(self, vts_host):
        vts_host.r_curl(url=self.vtc_image_url, checksum=self.vtc_image_checksum, loc_abs_path=self.vtc_image_abs_path)
        vts_host.r_curl(url=self.vtsr_image_url, checksum=self.vtsr_image_checksum, loc_abs_path=self.vtsr_image_abs_path)

    def deploy_vts(self, list_of_servers):
        from lab.nodes.vtf import Vtf
        from lab.nodes.vtc import VtsHost
        from lab.nodes.cimc_server import CimcController

        vts_hosts = filter(lambda host: type(host) is VtsHost, list_of_servers)
        if not vts_hosts:  # use controllers as VTS hosts if no special servers for VTS provided
            vts_hosts = filter(lambda host: type(host) is CimcController, list_of_servers)
        if not vts_hosts:
            raise RuntimeError('Neither special VTS hosts no controllers was provided')

        # map(lambda x: self.download_vts_images(x), vts_hosts) TODO: uncomment this

        for vts_host in vts_hosts:
            self.install_needed_rpms(vts_host)
            self.make_netsted_libvirt(vts_host=vts_host)
            self.make_openvswitch(vts_host)

            map(lambda x: self.deploy_single_vtc(vts_host=x), vts_hosts)

        self.make_cluster(vts_hosts=vts_hosts)

        map(lambda x: self.deploy_single_vtsr(vts_host=x), vts_hosts)

#        vtsr[0].r_xrnc_wait_all_online(100)

#        vts_hosts[0].pod.r_collect_information(regex='ERROR', comment='after_all_xrnc_vm_started')

#        if not vtcs[0].r_is_xrns_registered():
#            map(lambda dl: dl.r_xrnc_set_mtu(), xrncs)  # https://cisco.jiveon.com/docs/DOC-1455175 Step 12 about MTU
#            dl_server_status = map(lambda dl: dl.r_xrnc_start_dl(), xrncs)  # https://cisco.jiveon.com/docs/DOC-1455175 Step 11
#            if not all(dl_server_status):
#                raise RuntimeError('Failed to start DL servers')
#        else:
#            self.log('all XRNC are already deployed in the previous run')

        vts_hosts[0].pod.r_collect_information(regex='ERROR', comment='after_all_xrvr_registered')

#        vtcs[0].r_vtc_day0_config()
        vts_hosts[0].pod.r_collect_information(regex='ERROR', comment='after_day0_config')

        for vtf in filter(lambda y: type(y) is Vtf, list_of_servers):  # mercury-VTS this list is empty
            self.deploy_single_vtf(vtf)

        if not self.is_valid_installation(vts_hosts):
            raise RuntimeError('VTS installation is invalid')

    def delete_previous_libvirt_vms(self, vts_host):
        ans = vts_host.exe('virsh list')
        for role in ['xrnc', 'vtc']:
            if role in ans:
                vts_host.exe('virsh destroy {role}'.format(role=role))
        ans = vts_host.exe('virsh list --all')
        for role in ['xrnc', 'vtc']:
            if role in ans:
                vts_host.exe('virsh undefine {role}'.format(role=role))
        vts_host.exe('rm -rf {}'.format(self.vts_service_dir))

    def make_cluster(self, vts_hosts):
        vtc_list = vts_hosts[0].pod.vtc
        if vtc_list[0].r_vtc_wait_cluster_formed():
            self.log('Cluster is already formed')
            return

        cisco_bin_dir = '/opt/cisco/package/vtc/bin/'
        for vtc in vtc_list:
            cfg_body = vtc.get_cluster_conf_body()  # https://cisco.jiveon.com/docs/DOC-1443548 VTS 2.2: L2 HA Installation Steps  Step 1
            vtc.r_put_string_as_file_in_dir(string_to_put=cfg_body, file_name='cluster.conf', in_directory=cisco_bin_dir)
            vtc.exe(command='sudo ./modify_host_vtc.sh', in_directory=cisco_bin_dir)  # https://cisco.jiveon.com/docs/DOC-1443548 VTS 2.2: L2 HA Installation Steps  Step 2
        for vtc in vtc_list:
            vtc.exe(command='sudo ./cluster_install.sh', in_directory=cisco_bin_dir)  # https://cisco.jiveon.com/docs/DOC-1443548 VTS 2.2: L2 HA Installation Steps  Step 3

        vtc_list[0].exe(command='sudo ./master_node_install.sh', in_directory=cisco_bin_dir)  # https://cisco.jiveon.com/docs/DOC-1443548 VTS 2.2: L2 HA Installation Steps  Step 4

        if vtc_list[0].r_vtc_wait_cluster_formed(n_retries=100):
            return  # cluster is successfully formed
        else:
            raise RuntimeError('Failed to form VTC cluster after 100 attempts')

    def install_needed_rpms(self, vts_host):
        if self.vts_images_url not in vts_host.exe(command='cat VTS-VERSION', is_warn_only=True):
            self.log('Installing  needed RPMS...')
            # vts_host.r_register_rhel(self._rhel_creds_location)
            vts_host.exe(command='sudo yum update -y -q')
            # vts_host.exe('yum groupinstall "Virtualization Platform" -y -q')
            vts_host.exe('yum install libvirt genisoimage qemu-kvm-rhev expect sshpass openvswitch -y -q')
            vts_host.exe('systemctl start libvirtd')
            vts_host.exe('systemctl start openvswitch')
            vts_host.r_put_string_as_file_in_dir(string_to_put='VTS from {}\n'.format(self.vts_images_url), file_name='VTS-VERSION')
            self.log('RPMS are installed')
        else:
            self.log('All needed RPMS are already installed in the previous run')

    @staticmethod
    def make_netsted_libvirt(vts_host):
        if vts_host.exe('cat /sys/module/kvm_intel/parameters/nested') == 'N':
            vts_host.exe('echo options kvm-intel nested=1 > /etc/modprobe.d/kvm-intel.conf')
            vts_host.exe('rmmod kvm_intel')
            vts_host.exe('modprobe kvm_intel')
            if vts_host.exe('cat /sys/module/kvm_intel/parameters/nested') != 'Y':
                raise RuntimeError('Failed to set libvirt to nested mode')

    def make_openvswitch(self, vts_host):
        for nic_name in ['a', 'mx', 't']:
            nic = vts_host.get_nic(nic_name)
            if 'br-{}'.format(nic_name) not in vts_host.exe('ovs-vsctl show'):
                vts_host.exe('ovs-vsctl add-br br-{0} && ip l s dev br-{0} up'.format(nic_name))
                ip_nic, _ = nic.get_ip_and_mask()
                net_bits = nic.get_net().get_prefix_len()
                default_route_part = '&& ip r a default via {}'.format(nic.get_net().get_gw()) if nic.is_ssh() else ''
                vts_host.exe('ip a flush dev {n} && ip a a {ip}/{nb} dev br-{n} && ovs-vsctl add-port br-{n} {n} {rp}'.format(n=nic_name, ip=ip_nic, nb=net_bits, rp=default_route_part))
                vts_host.exe('ip l a dev vlan{} type dummy'.format(nic.get_vlan_id()))
                vts_host.exe('ovs-vsctl add-port br-{} vlan{}'.format(nic_name, nic.get_vlan_id()))
                vts_host.exe('ovs-vsctl set interface vlan{} type=internal'.format(nic.get_vlan_id()))
                vts_host.exe('ip l s dev vlan{} up'.format(nic.get_vlan_id()))
            else:
                self.log('Bridge br-{} is already created in the previous run'.format(nic_name))

    def deploy_single_vtc(self, vts_host):
        from lab.nodes.vtc import Vtc
        vtc = filter(lambda x: type(x) is Vtc, vts_host.virtual_servers)[0]
        if self.is_force_redeploy or not vtc.ping():
            self.delete_previous_libvirt_vms(vts_host=vts_host)
            cfg_body, net_part = vtc.get_config_and_net_part_bodies()

            config_iso_path = self.vts_service_dir + '/vtc_config.iso'
            config_txt_path = vts_host.r_put_string_as_file_in_dir(string_to_put=cfg_body, file_name='config.txt', in_directory=self.vts_service_dir)
            vts_host.exe('mkisofs -o {iso} {txt}'.format(iso=config_iso_path, txt=config_txt_path))

            self.run_virsh(virtual=vtc, iso_path=config_iso_path, net_part=net_part)
            vtc.vtc_change_default_password()
        else:
            self.log('Vtc {} is already deployed in the previous run.'.format(vtc))

    def deploy_single_vtsr(self, vts_host):
        from lab.nodes.vtc import Vtc
        from lab.nodes.vtsr import Vtsr

        vtc = filter(lambda x: type(x) is Vtc, vts_host.virtual_servers)[0]
        vtsr = filter(lambda x: type(x) is Vtsr, vts_host.virtual_servers)[0]
        if 'vtsr' in vts_host.exe('virsh list'):
            self.log('{} is already deployed in the previous run.'.format(vtsr))
            return

        cfg_body, net_part = vtsr.get_config_and_net_part_bodies()
        iso_path = self.vts_service_dir + '/xrnc_cfg.iso'

        cfg_name = 'xrnc.cfg'
        vtc.r_put_string_as_file_in_dir(string_to_put=cfg_body, file_name=cfg_name)
        vtc.exe('cp /opt/cisco/package/vts/bin/build_vts_config_iso.sh $HOME')
        vtc.exe('./build_vts_config_iso.sh xrnc {}'.format(cfg_name))  # https://cisco.jiveon.com/docs/DOC-1455175 step 8: use sudo /opt/cisco/package/vts/bin/build_vts_config_iso.sh xrnc xrnc.cfg
        ip, username, password = vtc.get_ssh()
        vts_host.exe('sshpass -p {p} scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {u}@{ip}:xrnc_cfg.iso {d}'.format(p=password, u=username, ip=ip, d=self.vts_service_dir))

        self.run_virsh(virtual=vtsr, iso_path=iso_path, net_part=net_part)

    def run_virsh(self, virtual, iso_path, net_part):
        disk_part = self.disk_part_tmpl.format(qcow_path='XXXXX', iso_path=iso_path)
        domain_body = self.libvirt_domain_tmpl.format(hostname=virtual.role, disk_part=disk_part, net_part=net_part, emulator='/usr/libexec/qemu-kvm')
        domain_xml_path = virtual.r_put_string_as_file_in_dir(string_to_put=domain_body, file_name='{0}_domain.xml'.format(virtual.role), in_directory=self.vts_service_dir)

        virtual.hard.exe('virsh define {xml} && virsh start {role} && virsh autostart {role}'.format(xml=domain_xml_path, role=virtual.role))

    def deploy_single_vtf(self, vtf):
        net_part, cfg_body = vtf.get_domain_andconfig_body()
        compute = vtf.get_ocompute()
        config_iso_path = self.vts_service_dir + '/vtc_config.iso'
        config_txt_path = compute.r_put_string_as_file_in_dir(string_to_put=cfg_body, file_name='system.cfg', in_directory=self.vts_service_dir)
        compute.exe('mkisofs -o {iso} {txt}'.format(iso=config_iso_path, txt=config_txt_path))
        self.run_virsh(virtual=vtf, iso_path=config_iso_path, net_part=net_part)

        # on VTC ncs_cli: configure set devices device XT{TAB} asr -- bgp[TAB] bgp-asi 23 commit
        # on DL ps -ef | grep dl -> then restart dl_vts_reg.py

    def execute(self, servers_and_clouds):
        self.deploy_vts(list_of_servers=servers_and_clouds['servers'])
        return True

    @staticmethod
    def is_valid_installation(vts_hosts):
        import requests

        from lab.nodes.vtc import Vtc

        vtc = vts_hosts[0].lab().get_nodes_by_class(Vtc)[0]
        try:
            return len(vtc.r_vtc_get_xrvrs()) == 2
        except requests.exceptions.ConnectTimeout:
            return False
