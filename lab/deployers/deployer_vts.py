from lab.deployers import Deployer


class DeployerVts(Deployer):

    def sample_config(self):
        return {'images-location': 'http://172.29.173.233/vts/nightly-2016-03-14/'}

    def __init__(self, config):
        super(DeployerVts, self).__init__(config=config)

        self._vtc_config_tmpl = self.read_config_from_file(config_path='vtc_vm_config.txt', directory='vts', is_as_string=True)
        self._xrnc_config_tmpl = self.read_config_from_file(config_path='xrnc_vm_config.txt', directory='vts', is_as_string=True)
        self._vtf_config_tmpl = self.read_config_from_file(config_path='vtf_vm_config.txt', directory='vts', is_as_string=True)
        self._libvirt_domain_tmpl = self.read_config_from_file(config_path='domain_template.txt', directory='libvirt', is_as_string=True)
        self._images_location = config['images-location']

    def deploy_vts(self, list_of_servers):
        from netaddr import IPNetwork

        controllers = filter(lambda x: 'control' in x.role(), list_of_servers)
        computes = filter(lambda x: 'compute' in x.role(), list_of_servers)

        if not controllers:
            raise RuntimeError('No cloud controllers was provided')

        if not computes:
            raise RuntimeError('No cloud computes was provided')

        controller = controllers[0]

        lab_name = str(controller.lab())
        ssh_net = controller.lab().get_ssh_net()
        ssh_prefixlen = ssh_net.prefixlen
        loc_net = IPNetwork('10.11.12.0/24')
        loc_prefixlen = loc_net.prefixlen
        ssh_username, ssh_password = controller.lab().get_common_ssh_creds()

        controller.run('yum groupinstall "Virtualization Platform" -y')

        vts_service_dir = '/tmp/vts_preparation'
        if controller.run('cat /sys/module/kvm_intel/parameters/nested') == 'N':
            controller.run('echo "options kvm-intel nested=1" | sudo tee /etc/modprobe.d/kvm-intel.conf')
            controller.run('rmmod kvm_intel')
            controller.run('modprobe kvm_intel')
            if controller.run('cat /sys/module/kvm_intel/parameters/nested') != 'Y':
                raise RuntimeError('Failed to set libvirt to nested mode')

        disk_part_template = '''
<disk type='file' device='disk'>
    <driver name='qemu' type='qcow2'/>
    <source file='{qcow_path}'/>
    <target dev='vda' bus='virtio'/>
</disk>

<disk type='file' device='cdrom'>
    <driver name='qemu' type='raw'/>
    <source file='{iso_path}'/>
    <target dev='hdc' bus='ide'/>
</disk>
'''

        net_part_template_vtc = '''
<interface type='bridge'>
     <source bridge='br-ex'/>
     <virtualport type='openvswitch'/>
     <target dev='{role}-public'/>
     <model type='virtio'/>
</interface>
<interface type='bridge'>
     <source bridge='br-inst'/>
     <vlan>
       <tag id='{vlan}'/>
     </vlan>
     <virtualport type='openvswitch'/>
     <target dev='{role}-private'/>
     <model type='virtio'/>
</interface>
'''

        net_part_template_xrnc = '''
<interface type='bridge'>
     <source bridge='br-inst'/>
     <vlan>
       <tag id='{vlan}'/>
     </vlan>
     <virtualport type='openvswitch'/>
     <target dev='{role}-private'/>
     <model type='virtio'/>
</interface>
<interface type='bridge'>
     <source bridge='br-ex'/>
     <virtualport type='openvswitch'/>
     <target dev='{role}-public'/>
     <model type='virtio'/>
</interface>
'''

        net_part_template_vtf = '''
<interface type='bridge'>
     <source bridge='br-inst'/>
     <vlan>
       <tag id='{vlan}'/>
     </vlan>
     <virtualport type='openvswitch'/>
     <target dev='{role}-private'/>
     <model type='virtio'/>
</interface>
<interface type='bridge'>
     <source bridge='br-int'/>
     <virtualport type='openvswitch'/>
     <target dev='{role}-public'/>
     <model type='virtio'/>
</interface>
'''

        dns_ip, ntp_ip = '171.70.168.183', '171.68.38.66'
        ssh_netmask, ssh_gw = ssh_net.netmask, str(ssh_net[1])
        loc_netmask, loc_gw = loc_net.netmask, str(loc_net[1])

        ips = {'vtc': {'ssh_ip': str(ssh_net[31]), 'loc_ip': str(loc_net[9])},
               'xrnc': {'ssh_ip_dl': str(ssh_net[26]), 'ssh_ip_xrvr': str(ssh_net[27]), 'loc_ip_dl': str(loc_net[4]), 'loc_ip_xrvr': str(loc_net[5])}}

        compute_n =0
        for i, role in enumerate([] + ['vtf'] * 3):
            if role == 'vtc':
                config_body = self._vtc_config_tmpl.format(ssh_ip=ips[role]['ssh_ip'], ssh_netmask=ssh_netmask, ssh_gw=ssh_gw, loc_ip=ips[role]['loc_ip'], loc_netmask=loc_netmask, dns_ip=dns_ip, ntp_ip=ntp_ip,
                                                           username=ssh_username, password=ssh_password, lab_name=lab_name)
                run_on_server = controller
                config_file_name = 'config.txt'  # this name is required by vtc.qcow2
                net_part = net_part_template_vtc.format(vlan=3777, role=role)

            elif role == 'xrnc':
                config_body = self._xrnc_config_tmpl.format(ssh_ip_dl=ips[role]['ssh_ip_dl'], ssh_ip_xrvr=ips[role]['ssh_ip_xrvr'], ssh_netmask=ssh_netmask, ssh_prefixlen=ssh_prefixlen, ssh_gw=ssh_gw,
                                                            loc_ip_dl=ips[role]['loc_ip_dl'], loc_ip_xrvr=ips[role]['loc_ip_xrvr'], loc_netmask=loc_netmask, loc_prefixlen=loc_prefixlen, dns_ip=dns_ip, ntp_ip=ntp_ip,
                                                            vtc_ssh_ip=ips['vtc']['ssh_ip'], username=ssh_username, password=ssh_password, lab_name=lab_name)
                run_on_server = controller
                config_file_name = 'system.cfg'  # this name is required by xrnc.qcow2
                net_part = net_part_template_xrnc.format(vlan=3777, role=role)
            elif role == 'vtf':
                run_on_server = computes[compute_n]
                compute_hostname = run_on_server.hostname()
                config_body = self._vtf_config_tmpl.format(loc_ip=loc_net[61 + compute_n], loc_netmask=loc_netmask, loc_gw=loc_gw, dns_ip=dns_ip, ntp_ip=ntp_ip,
                                                           vtc_loc_ip=ips['vtc']['loc_ip'], username=ssh_username, password=ssh_password, compute_hostname=compute_hostname)
                config_file_name = 'system.cfg'  # this name is required by vtf.qcow2
                net_part = net_part_template_vtf.format(vlan=3777, role=role)
                compute_n += 1
            else:
                raise ValueError('No role "{0}"'.format(role))

            config_iso_path = vts_service_dir + '/{0}_config.iso'.format(role)
            config_txt_path = run_on_server.put_string_as_file_in_dir(string_to_put=config_body, file_name=config_file_name, in_directory=vts_service_dir)
            run_on_server.run('mkisofs -o {iso} {txt}'.format(iso=config_iso_path, txt=config_txt_path))
            run_on_server.run('mv {0} {1}_config.txt'.format(config_file_name, role), in_directory=vts_service_dir)

            image_url = self._images_location + role + '.qcow2'
            check_sum = run_on_server.run('curl {0}'.format(image_url + '.sha256sum.txt')).split()[0]
            qcow_file = run_on_server.wget_file(url=image_url, to_directory=vts_service_dir, checksum=check_sum)

            disk_part = disk_part_template.format(qcow_path=qcow_file, iso_path=config_iso_path)
            domain_body = self._libvirt_domain_tmpl.format(hostname=role, disk_part=disk_part, net_part=net_part, emulator='/usr/libexec/qemu-kvm')
            domain_xml_path = run_on_server.put_string_as_file_in_dir(string_to_put=domain_body, file_name='{0}_domain.xml'.format(role), in_directory=vts_service_dir)
            # run_on_server.run('virsh create {0}'.format(domain_xml_path))
            # ovs-vsctl add-port br-inst vlan3777
            # ovs-vsctl set interface vlan3777 type=internal
            # ovs-vsctl set port vlan3777 tag=3777
            # ovs-vsctl show
            # ip l set dev vlan3777 up
            # ip a a 10.11.12.set dev vlan3777 up
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
