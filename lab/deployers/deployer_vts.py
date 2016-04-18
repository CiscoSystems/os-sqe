from lab.deployers import Deployer


class DeployerVts(Deployer):

    def sample_config(self):
        return {'images-location': 'http://172.29.173.233/vts/nightly-2016-03-14/'}

    def __init__(self, config):
        super(DeployerVts, self).__init__(config=config)

        self._config_tmpl = self.read_config_from_file(config_path='vtc_vm_config.txt', directory='vts', is_as_string=True)
        self._libvirt_domain_tmpl = self.read_config_from_file(config_path='domain_template.txt', directory='libvirt', is_as_string=True)
        self._images_location = config['images-location']

    def deploy_vts(self, list_of_servers):
        controllers = filter(lambda x: 'controller' in str(x), list_of_servers)

        if not controllers:
            raise RuntimeError('No cloud controllers was provided')

        controller = controllers[0]

        ssh_net = controller.lab().get_ssh_net()
        ssh_ip, ssh_netmask, ssh_gw = str(ssh_net[12]), ssh_net.netmask, str(ssh_net[1])
        ssh_username, ssh_password = controller.lab().get_common_ssh_creds()

        config_body = self._config_tmpl.format(ssh_ip=ssh_ip, ssh_netmask=ssh_netmask, ssh_gw=ssh_gw,
                                               loc_ip='172.16.16.1', loc_netmask='255.255.255.0', dns='171.70.168.183',
                                               vtc_username=ssh_username, vtc_password=ssh_password)

        vts_service_dir = '/tmp/vts'

        vtc_config_txt_path = controller.put_string_as_file_in_dir(string_to_put=config_body, file_name='vtc_config.txt', in_directory=vts_service_dir)

        vtc_config_iso_path = vts_service_dir + '/vtc_config.iso'
        controller.run('mkisofs -o {iso} {txt}'.format(iso=vtc_config_iso_path, txt=vtc_config_txt_path))

        qcow_files = []
        for image in ['vtc.qcow2', 'vtf.qcow2', 'xrnc.qcow2']:
            check_sum_file = image + '.sha256sum.txt'
            ans = controller.run('curl {0}'.format(self._images_location + check_sum_file))
            check_sum = ans.split()[0]
            qcow_files.append(controller.wget_file(url=self._images_location + image, to_directory=vts_service_dir, checksum=check_sum))

        disk_part = '''
<disk type='file' device='disk'>
    <driver name='qemu' type='qcow2'/>
    <source file='{vtc_qcow_path}'/>
    <target dev='vda' bus='virtio'/>
</disk>

<disk type='file' device='cdrom'>
    <driver name='qemu' type='raw'/>
    <source file='{vtc_config_iso_path}'/>
    <target dev='hdc' bus='ide'/>
</disk>
'''.format(vtc_qcow_path=qcow_files[0], vtc_config_iso_path=vtc_config_iso_path)

        net_part = '''
<interface type='bridge'>
      <source bridge='br-ex'/>
      <virtualport type='openvswitch'>
      </virtualport>
      <target dev='vnc-public'/>
      <model type='virtio'/>
      <alias name='kir0'/>
</interface>
<interface type='bridge'>
     <source bridge='br-int'/>
      <virtualport type='openvswitch'>
      </virtualport>
      <target dev='vnc-private'/>
      <model type='virtio'/>
      <alias name='kir1'/>
</interface>
'''
        domain_body = self._libvirt_domain_tmpl.format(hostname='VTC', disk_part=disk_part, net_part=net_part)
        vtc_domain_xml_path = controller.put_string_as_file_in_dir(string_to_put=domain_body, file_name='vtc_domain.xml', in_directory=vts_service_dir)
        controller.run('virsh create {0}'.format(vtc_domain_xml_path))

    def wait_for_cloud(self, list_of_servers):
        self.deploy_vts(list_of_servers=list_of_servers)
