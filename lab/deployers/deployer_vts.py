from lab.deployers import Deployer


class DeployerVts(Deployer):

    def sample_config(self):
        return {'images-location': 'http://172.29.173.233/vts/nightly-2016-03-14/', 'rhel-subsription-creds': 'http://wwwin-nfv-orch.cisco.com/mercury/latest/ver-1.0.2/'}

    def __init__(self, config):
        super(DeployerVts, self).__init__(config=config)
        import requests
        import json

        self._rhel_creds_source = config['rhel-subsription-creds']
        text = requests.get(self._rhel_creds_source).text
        rhel_json = json.loads(text)
        self._rhel_username = rhel_json['rhel-username']
        self._rhel_password = rhel_json['rhel-password']
        self._rhel_pool_id = rhel_json['rhel-pool-id']

        self._vts_service_dir = '/tmp/vts_preparation'

        self._libvirt_domain_tmpl = self.read_config_from_file(config_path='domain_template.txt', directory='libvirt', is_as_string=True)
        self._disk_part_tmpl = self.read_config_from_file(config_path='disk-part-of-libvirt-domain.template', directory='vts', is_as_string=True)

        self._vts_images_location = config['images-location']

    def deploy_vts(self, list_of_servers):
        from lab.vts_classes.vtf import Vtf
        from lab.vts_classes.vtc import VtsHost
        # according to https://cisco.jiveon.com/docs/DOC-1443548

        vts_hosts = filter(lambda x: type(x) is VtsHost, list_of_servers) or filter(lambda x: 'control' in x.role(), list_of_servers)
        if not vts_hosts:  # use controllers as VTS hosts if no special servers for VTS provided
            raise RuntimeError('Neither specival VTS hosts no controllers was provided')

        for vts_host in vts_hosts:
            vts_host.put_string_as_file_in_dir(string_to_put='VTS from {}\n'.format(self._vts_images_location), file_name='VTS-VERSION')
            self.deploy_single_vtc_an_xrvr(vts_host)

        for vtf in filter(lambda x: type(x) is Vtf, list_of_servers):
            self.deploy_single_vtf(vtf)

    def _common_prepare_host(self, server):
        repos_to_enable = ['--enable=rhel-7-server-rpms',
                           '--enable=rhel-7-server-optional-rpms',
                           '--enable=rhel-7-server-extras-rpms',
                           '--enable=rhel-7-server-openstack-7.0-rpms',
                           '--enable=rhel-7-server-openstack-7.0-director-rpms']
        status = server.run(command='subscription-manager status', warn_only=True)
        if 'Overall Status: Current' not in status:
            server.run(command='sudo subscription-manager register --username={0} --password={1}'.format(self._rhel_username, self._rhel_password))
            available_pools = server.run(command='sudo subscription-manager list --available')
            if self._rhel_pool_id not in available_pools:
                raise ValueError('Provided RHEL pool id "{}" is not in the list of available pools, plz check your RHEL credentials here {}'.format(self._rhel_pool_id, self._rhel_creds_source))

            server.run(command='sudo subscription-manager attach --pool={0}'.format(self._rhel_pool_id))
            server.run(command='sudo subscription-manager repos --disable=*')
            server.run(command='sudo subscription-manager repos ' + ' '.join(repos_to_enable))
        server.run(command='sudo yum update -y')
        server.run('yum groupinstall "Virtualization Platform" -y')
        server.run('yum install genisoimage openvswitch -y')

        if server.run('cat /sys/module/kvm_intel/parameters/nested') == 'N':
            server.run('echo "options kvm-intel nested=1" | sudo tee /etc/modprobe.d/kvm-intel.conf')
            server.run('rmmod kvm_intel')
            server.run('modprobe kvm_intel')
            if server.run('cat /sys/module/kvm_intel/parameters/nested') != 'Y':
                raise RuntimeError('Failed to set libvirt to nested mode')
        server.run('systemctl start libvirtd')
        server.run('systemctl start openvswitch')

    def deploy_single_vtc_an_xrvr(self, vts_host):
        from lab.vts_classes.xrvr import Xrvr
        from lab.vts_classes.vtc import Vtc

        self._common_prepare_host(vts_host)

        vtc, xrvr = None, None
        for wire in vts_host.get_all_wires():
            peer_node = wire.get_peer_node(self)
            if type(peer_node) is Vtc:
                vtc = peer_node
            if type(peer_node) is Xrvr:
                xrvr = peer_node

        for nic in filter(lambda x: x.is_vts() or x.is_ssh(),  vts_host.get_nics().values()):
            if 'br-'.format(nic.get_name()) not in vts_host.run('ovs-vsctl show'):
                vts_host.run('ovs-vsctl add-br br-{}'.format(nic.get_name()))
                ip, _ = nic.get_ip_netmask()
                net_pref = nic.get_net().prefixlen
                vts_host.run('ip a flush dev {n} && ip a a {ip}/{net_pref} dev {n} && ovs-vsctl add-port br-{n} {n}'.format(n=nic.get_name(), ip=ip, net_pref=net_pref))
                if nic.is_vts():
                    vts_host.run('ip l a dev vlan{} type dummy'.format(nic.get_vlan()))
                    vts_host.run('ovs-vsctl add-port br-{} vlan{}'.format(nic.get_name(), nic.get_vlan()))
                    vts_host.run('ovs-vsctl set interface vlan{} type=internal'.format(nic.get_vlan()))
                    vts_host.run('ovs-vsctl set port vlan{0} tag={0}'.format(nic.get_vlan()))
                    vts_host.run('ip l s dev vlan{} up'.format(nic.get_vlan()))

        cfg_body, net_part = vtc.get_config_and_net_part_bodies()
        self._common_part(server=vts_host, role='vtc', config_file_name='config.txt', config_body=cfg_body, net_part=net_part)

        cfg_body, net_part = xrvr.get_config_and_net_part_bodies()
        self._common_part(server=vts_host, role='XRVR', config_file_name='system.cfg', config_body=cfg_body, net_part=net_part)

    def _common_part(self, server, role, config_file_name, config_body, net_part):
            config_iso_path = self._vts_service_dir + '/{0}_config.iso'.format(role)
            config_txt_path = server.put_string_as_file_in_dir(string_to_put=config_body, file_name=config_file_name, in_directory=self._vts_service_dir)
            server.run('mkisofs -o {iso} {txt}'.format(iso=config_iso_path, txt=config_txt_path))
            server.run('mv {0} {1}_config.txt'.format(config_file_name, role), in_directory=self._vts_service_dir)

            image_url = self._vts_images_location + role + '.qcow2'
            qcow_file = server.wget_file(url=image_url, to_directory=self._vts_service_dir, checksum=None)

            disk_part = self._disk_part_tmpl.format(qcow_path=qcow_file, iso_path=config_iso_path)
            domain_body = self._libvirt_domain_tmpl.format(hostname=role, disk_part=disk_part, net_part=net_part, emulator='/usr/libexec/qemu-kvm')
            domain_xml_path = server.put_string_as_file_in_dir(string_to_put=domain_body, file_name='{0}_domain.xml'.format(role), in_directory=self._vts_service_dir)

            server.run('virsh create {0}'.format(domain_xml_path))

    def deploy_single_vtf(self, vtf):
        net_part, config_body = vtf.get_domain_andconfig_body()
        compute = vtf.get_ocompute()
        self._common_part(server=compute, role='vtf', config_file_name='system.cfg', config_body=config_body, net_part=net_part)

        # sun in DL sudo /opt/cisco/package/sr/bin/setupXRNC_HA.sh 0.0.0.0
        # on VTC: cat /var/log/ncs/localhost:8888.access
        # on VTC ncs_cli: configure set devices device XT{TAB} asr -- bgp[TAB] bgp-asi 23 commit
        # on VTC ncs_cli: show running-config evpn
        # on DL cat /etc/vpe/vsocsr/dl_server.ini
        # on DL ps -ef | grep dl -> then restart dl_vts_reg.py
        # on switch :
        # sh running - config | i feature
        # install feature-set fex
        # allow feature-set fex
        # feature - set fex
        # feature telnet
        # feature nxapi
        # feature bash-shell
        # feature ospf
        # feature bgp
        # feature pim
        # feature interface-vlan
        # feature vn-segment-vlan-based
        # feature lacp
        # feature dhcp
        # feature vpc
        # feature lldp
        # feature nv overlay

    def wait_for_cloud(self, list_of_servers):
        self.deploy_vts(list_of_servers=list_of_servers)
