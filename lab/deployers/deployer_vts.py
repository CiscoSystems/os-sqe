from lab.deployers import Deployer


class DeployerVts(Deployer):

    def sample_config(self):
        return {'images-location': 'http://172.29.173.233/vts/nightly-2016-03-14/'}

    def __init__(self, config):
        super(DeployerVts, self).__init__(config=config)

        self._vts_service_dir = '/tmp/vts_preparation'
        
        self._vtc_config_tmpl = self.read_config_from_file(config_path='vtc_vm_config.txt', directory='vts', is_as_string=True)
        self._vtc_net_part_tmpl = self.read_config_from_file(config_path='vtc-net-part-of-libvirt-domain.template', directory='vts', is_as_string=True)
        
        self._xrnc_config_tmpl = self.read_config_from_file(config_path='xrnc_vm_config.txt', directory='vts', is_as_string=True)
        self._xrnc_net_part_tmpl = self.read_config_from_file(config_path='xrnc-net-part-of-libvirt-domain.template', directory='vts', is_as_string=True)

        self._libvirt_domain_tmpl = self.read_config_from_file(config_path='domain_template.txt', directory='libvirt', is_as_string=True)
        self._disk_part_tmpl = self.read_config_from_file(config_path='disk-part-of-libvirt-domain.template', directory='vts', is_as_string=True)

        self._images_location = config['images-location']

    def deploy_vts(self, list_of_servers):
        from lab.vts import VtsHost

        vts_hosts = filter(lambda x: type(x) is VtsHost, list_of_servers) or filter(lambda x: 'control' in x.role(), list_of_servers)
        if not vts_hosts:  # use controllers as VTS hosts if no special servers for VTS provided
            raise RuntimeError('Neither specival VTS hosts no controllers was provided')

        computes = filter(lambda x: 'compute' in x.role(), list_of_servers)

        for vts_host in vts_hosts:
            self.deploy_single_vtc_an_xrvr(vts_host)

        if not computes:
            raise RuntimeError('No cloud computes was provided')

    @staticmethod
    def _common_prepare_host(server):
        server.run('yum groupinstall "Virtualization Platform" -y')

        if server.run('cat /sys/module/kvm_intel/parameters/nested') == 'N':
            server.run('echo "options kvm-intel nested=1" | sudo tee /etc/modprobe.d/kvm-intel.conf')
            server.run('rmmod kvm_intel')
            server.run('modprobe kvm_intel')
            if server.run('cat /sys/module/kvm_intel/parameters/nested') != 'Y':
                raise RuntimeError('Failed to set libvirt to nested mode')

    def deploy_single_vtc_an_xrvr(self, vts_host, vtc, xrvr):
        from netaddr import IPNetwork

        self._common_prepare_host(server)
        lab_name = str(server.lab())
        ssh_net = server.lab().get_ssh_net()
        ssh_prefixlen = ssh_net.prefixlen
        loc_net = IPNetwork('10.11.12.0/24')
        loc_prefixlen = loc_net.prefixlen
        ssh_username, ssh_password = None, None

        ssh_netmask, ssh_gw = ssh_net.netmask, str(ssh_net[1])
        loc_netmask, loc_gw = loc_net.netmask, str(loc_net[1])

        ips = {'vtc': {'ssh_ip': str(ssh_net[31]), 'loc_ip': str(loc_net[9])},
               'xrnc': {'ssh_ip_dl': str(ssh_net[26]), 'ssh_ip_xrvr': str(ssh_net[27]), 'loc_ip_dl': str(loc_net[4]), 'loc_ip_xrvr': str(loc_net[5])}}

        vtc_ip, vtc_username, vtc_password = vtc.get_ssh()

        xrvr_ip, xrvr_username, xrvr_password = xrvr.get_ssh()
        vtc_iso_cfg = self._vtc_config_tmpl.format(ssh_ip=ips['vtc']['ssh_ip'], ssh_netmask=ssh_netmask, ssh_gw=ssh_gw, loc_ip=ips['vtc']['loc_ip'], loc_netmask=loc_netmask, dns_ip=dns_ip, ntp_ip=ntp_ip,
                                                   username=ssh_username, password=ssh_password, lab_name=lab_name)

        net_part = self._vtc_net_part_tmpl.format(vlan=3777)
        self._common_part(server=vts_host, role='vtc', config_file_name='config.txt', config_body=vtc_iso_cfg, net_part=net_part)


        xrnc_iso_cfg = self._xrnc_config_tmpl.format(ssh_ip_dl=ips['xrnc']['ssh_ip_dl'], ssh_ip_xrvr=ips['role']['ssh_ip_xrvr'], ssh_netmask=ssh_netmask, ssh_prefixlen=ssh_prefixlen, ssh_gw=ssh_gw,
                                                     loc_ip_dl=ips['role']['loc_ip_dl'], loc_ip_xrvr=ips['role']['loc_ip_xrvr'], loc_netmask=loc_netmask, loc_prefixlen=loc_prefixlen, dns_ip=dns_ip, ntp_ip=ntp_ip,
                                                     vtc_ssh_ip=ips['vtc']['ssh_ip'], username=ssh_username, password=ssh_password, lab_name=lab_name)
        net_part = self._xrnc_net_part_tmpl.format(vlan=3777)
        self._common_part(server=vts_host, role='xrnc', config_file_name='system.cfg', config_body=xrnc_iso_cfg, net_part=net_part)

    def _common_part(self, server, role, config_file_name, config_body, net_part):
            config_iso_path = self._vts_service_dir + '/{0}_config.iso'.format(role)
            config_txt_path = server.put_string_as_file_in_dir(string_to_put=config_body, file_name=config_file_name, in_directory=self._vts_service_dir)
            server.run('mkisofs -o {iso} {txt}'.format(iso=config_iso_path, txt=config_txt_path))
            server.run('mv {0} {1}_config.txt'.format(config_file_name, role), in_directory=self._vts_service_dir)

            image_url = self._images_location + role + '.qcow2'
            check_sum = server.run('curl {0}'.format(image_url + '.sha256sum.txt')).split()[0]
            qcow_file = server.wget_file(url=image_url, to_directory=self._vts_service_dir, checksum=check_sum)

            disk_part = self._disk_part_tmpl.format(qcow_path=qcow_file, iso_path=config_iso_path)
            domain_body = self._libvirt_domain_tmpl.format(hostname=role, disk_part=disk_part, net_part=net_part, emulator='/usr/libexec/qemu-kvm')
            domain_xml_path = server.put_string_as_file_in_dir(string_to_put=domain_body, file_name='{0}_domain.xml'.format(role), in_directory=self._vts_service_dir)

            server.run('virsh create {0}'.format(domain_xml_path))

    def deploy_single_vtf(self, vtf):
        net_part, config_body = vtf.get_domain_andconfig_body()
        compute = vtf.get_ocompute()
        self._common_part(server=compute, role='vtf', config_file_name='system.cfg', config_body=config_body, net_part=net_part)

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
