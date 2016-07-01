from lab.deployers import Deployer


class DeployerVts(Deployer):

    def sample_config(self):
        return {'images-location': 'http://172.29.173.233/vts/nightly-2016-03-14/', 'rhel-subsription-creds': 'http://172.29.173.233/redhat/subscriptions/rhel-subscription-chandra.json'}

    def __init__(self, config):
        super(DeployerVts, self).__init__(config=config)

        self._rhel_creds_source = config['rhel-subsription-creds']

        self._vts_service_dir = '/tmp/vts_preparation'

        self._libvirt_domain_tmpl = self.read_config_from_file(config_path='domain_template.txt', directory='libvirt', is_as_string=True)
        self._disk_part_tmpl = self.read_config_from_file(config_path='disk-part-of-libvirt-domain.template', directory='vts', is_as_string=True)

        self._vts_images_location = config['images-location']

    def deploy_vts(self, list_of_servers):
        from lab.vts_classes.vtf import Vtf
        from lab.vts_classes.vtc import VtsHost
        from lab.cimc import CimcController
        from lab.vts_classes.xrvr import Xrvr
        from lab.vts_classes.vtc import Vtc

        vts_hosts = filter(lambda x: type(x) in [VtsHost, CimcController], list_of_servers)
        if not vts_hosts:  # use controllers as VTS hosts if no special servers for VTS provided
            raise RuntimeError('Neither specival VTS hosts no controllers was provided')

        for vts_host in vts_hosts:
            vtc, xrnc = None, None
            for wire in vts_host.get_all_wires():
                peer_node = wire.get_peer_node(self)
                if type(peer_node) is Vtc:
                    vtc = peer_node
            vts_host.put_string_as_file_in_dir(string_to_put='VTS from {}\n'.format(self._vts_images_location), file_name='VTS-VERSION')
            self._install_needed_rpms(vts_host)
            self._make_netsted_libvirt(vts_host=vts_host)
            self._delete_previous_libvirt_vms(vts_host=vts_host)
            self._make_openvswitch(vts_host)
            self.deploy_single_vtc(vts_host=vts_host, vtc=vtc)

        self.make_cluster(lab=vts_hosts[0].lab())

        for vts_host in vts_hosts:
            vtc, xrnc = None, None
            for wire in vts_host.get_all_wires():
                peer_node = wire.get_peer_node(self)
                if type(peer_node) is Vtc:
                    vtc = peer_node
                if type(peer_node) is Xrvr:
                    xrnc = peer_node
            self.deploy_single_xrnc(vts_host=vts_host, vtc=vtc, xrnc=xrnc)

        for vtf in filter(lambda x: type(x) is Vtf, list_of_servers):  # mercury-VTS this list is empty
            self.deploy_single_vtf(vtf)

    def _delete_previous_libvirt_vms(self, vts_host):
        ans = vts_host.run('virsh list')
        for role in ['XRNC', 'vtc']:
            if role in ans:
                vts_host.run('virsh destroy {}'.format(role))
        vts_host.run('rm -rf {}'.format(self._vts_service_dir))

    @staticmethod
    def make_cluster(lab):
        from time import sleep
        from lab.vts_classes.vtc import Vtc

        vtc_list = lab.get_nodes_by_class(Vtc)
        for vtc in vtc_list:
            cfg_body = vtc.get_cluster_conf_body()  # https://cisco.jiveon.com/docs/DOC-1443548 VTS 2.2: L2 HA Installation Steps  Step 1
            vtc.put_string_as_file_in_dir(string_to_put=cfg_body, file_name='cluster.conf', in_directory='/opt/cisco/package/vtc/bin')
            vtc.run(command='sudo /opt/cisco/package/vtc/bin/modify_host_vtc.sh')  # https://cisco.jiveon.com/docs/DOC-1443548 VTS 2.2: L2 HA Installation Steps  Step 2
        for vtc in vtc_list:
            vtc.run(command='sudo /opt/cisco/package/vtc/bin/cluster_install.sh')  # https://cisco.jiveon.com/docs/DOC-1443548 VTS 2.2: L2 HA Installation Steps  Step 3

        vtc_list[0].run(command='sudo /opt/cisco/package/vtc/bin/master_node_install.sh')  # https://cisco.jiveon.com/docs/DOC-1443548 VTS 2.2: L2 HA Installation Steps  Step 4
        for i in range(100):
            ans = vtc_list[0].vtc_get_cluster_info()
            if len(ans) == 2:
                return  # cluster is successfully formed
            sleep(10)
        raise RuntimeError('Failed to form VTC cluster after 100 attempts')

    def _install_needed_rpms(self, vts_host):
        vts_host.register_rhel(self._rhel_creds_source)
        vts_host.run(command='sudo yum update -y')
        vts_host.run('yum groupinstall "Virtualization Platform" -y')
        vts_host.run('yum install genisoimage openvswitch qemu-kvm -y')
        vts_host.run('subscription-manager unregister')
        vts_host.run('wget http://172.29.173.233/redhat/sshpass-1.05-1.el7.rf.x86_64.rpm')
        vts_host.run(command='rpm -ivh sshpass-1.05-1.el7.rf.x86_64.rpm', warn_only=True)
        vts_host.run(command='rm -f sshpass-1.05-1.el7.rf.x86_64.rpm')

        vts_host.run('systemctl start libvirtd')
        vts_host.run('systemctl start openvswitch')

    @staticmethod
    def _make_netsted_libvirt(vts_host):
        if vts_host.run('cat /sys/module/kvm_intel/parameters/nested') == 'N':
            vts_host.run('echo "options kvm-intel nested=1" | sudo tee /etc/modprobe.d/kvm-intel.conf')
            vts_host.run('rmmod kvm_intel')
            vts_host.run('modprobe kvm_intel')
            if vts_host.run('cat /sys/module/kvm_intel/parameters/nested') != 'Y':
                raise RuntimeError('Failed to set libvirt to nested mode')

    @staticmethod
    def _make_openvswitch(vts_host):
        for nic_name in ['a', 'mx', 't']:
            nic = vts_host.get_nic(nic_name)
            if 'br-{}'.format(nic.get_name()) not in vts_host.run('ovs-vsctl show'):
                vts_host.run('ovs-vsctl add-br br-{0} && ip l s dev br-{0} up'.format(nic.get_name()))
                ip_nic, _ = nic.get_ip_and_mask()
                net_bits = nic.get_net().prefixlen
                default_route_part = '&& ip r a default via {}'.format(nic.get_net()[1]) if nic.is_ssh() else ''
                vts_host.run('ip a flush dev {n} && ip a a {ip}/{nb} dev br-{n} && ovs-vsctl add-port br-{n} {n} {rp}'.format(n=nic.get_name(), ip=ip_nic, nb=net_bits, rp=default_route_part))
                vts_host.run('ip l a dev vlan{} type dummy'.format(nic.get_vlan()))
                vts_host.run('ovs-vsctl add-port br-{} vlan{}'.format(nic.get_name(), nic.get_vlan()))
                vts_host.run('ovs-vsctl set interface vlan{} type=internal'.format(nic.get_vlan()))
                vts_host.run('ip l s dev vlan{} up'.format(nic.get_vlan()))

    def deploy_single_vtc(self, vts_host, vtc):
        from fabric.api import prompt
        cfg_body, net_part = vtc.get_config_and_net_part_bodies()

        config_iso_path = self._vts_service_dir + '/vtc_config.iso'
        config_txt_path = vts_host.put_string_as_file_in_dir(string_to_put=cfg_body, file_name='config.txt', in_directory=self._vts_service_dir)
        vts_host.run('mkisofs -o {iso} {txt}'.format(iso=config_iso_path, txt=config_txt_path))

        self._get_image_and_run_virsh(server=vts_host, role='vtc', iso_path=config_iso_path, net_part=net_part)
        while True:
            ans = prompt('Got to WEB GUI  of {} as admin/admin and set provided oob password, type READY when finished> '.format(vtc))
            if ans == 'READY':
                break

    def deploy_single_xrnc(self, vts_host, vtc, xrnc):
        from fabric.api import prompt

        cfg_body, net_part = xrnc.get_config_and_net_part_bodies()
        iso_path = self._vts_service_dir + '/xrnc_cfg.iso'

        # https://cisco.jiveon.com/docs/DOC-1455175 step 8: use sudo /opt/cisco/package/vts/bin/build_vts_config_iso.sh xrnc xrnc.cfg
        cfg_name = 'xrnc.cfg'
        vtc.put_string_as_file_in_dir(string_to_put=cfg_body, file_name=cfg_name)
        vtc.run('cp /opt/cisco/package/vts/bin/build_vts_config_iso.sh $HOME')
        vtc.run('./build_vts_config_iso.sh xrnc {}'.format(cfg_name))
        ip, username, password = vtc.get_ssh()

        while True:
            ans = prompt('Go to {v} and scp {u}@{ip}:xrnc_cfg.iso {d} with  password {p}, type READY when finished'.format(p=password, u=username, ip=ip, d=self._vts_service_dir, v=vts_host))
            if ans == 'READY':
                break

        self._get_image_and_run_virsh(server=vts_host, role='XRNC', iso_path=iso_path, net_part=net_part)
        # xrnc.run('ip l s dev br-underlay mtu 1400')  # https://cisco.jiveon.com/docs/DOC-1455175 step 12 about MTU

    def _get_image_and_run_virsh(self, server, role, iso_path, net_part):
        image_url = self._vts_images_location + role + '.qcow2'
        qcow_file = server.wget_file(url=image_url, to_directory=self._vts_service_dir, checksum=None)

        disk_part = self._disk_part_tmpl.format(qcow_path=qcow_file, iso_path=iso_path)
        domain_body = self._libvirt_domain_tmpl.format(hostname=role, disk_part=disk_part, net_part=net_part, emulator='/usr/libexec/qemu-kvm')
        domain_xml_path = server.put_string_as_file_in_dir(string_to_put=domain_body, file_name='{0}_domain.xml'.format(role), in_directory=self._vts_service_dir)

        server.run('virsh create {0}'.format(domain_xml_path))

    def deploy_single_vtf(self, vtf):
        net_part, cfg_body = vtf.get_domain_andconfig_body()
        compute = vtf.get_ocompute()
        config_iso_path = self._vts_service_dir + '/vtc_config.iso'
        config_txt_path = compute.put_string_as_file_in_dir(string_to_put=cfg_body, file_name='system.cfg', in_directory=self._vts_service_dir)
        compute.run('mkisofs -o {iso} {txt}'.format(iso=config_iso_path, txt=config_txt_path))
        self._get_image_and_run_virsh(server=compute, role='vtf', iso_path=config_iso_path, net_part=net_part)

        # sun in DL sudo /opt/cisco/package/sr/bin/setupXRNC_HA.sh 0.0.0.0
        # on VTC: cat /var/log/ncs/localhost:8888.access
        # on VTC ncs_cli: configure set devices device XT{TAB} asr -- bgp[TAB] bgp-asi 23 commit
        # on VTC ncs_cli: show running-config evpn
        # on DL cat /etc/vpe/vsocsr/dl_server.ini
        # on DL ps -ef | grep dl -> then restart dl_vts_reg.py

    def wait_for_cloud(self, list_of_servers):
        self.deploy_vts(list_of_servers=list_of_servers)
