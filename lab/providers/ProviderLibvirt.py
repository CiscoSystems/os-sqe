from lab.providers import Provider
from lab.logger import lab_logger
from lab import decorators


class ProviderLibvirt(Provider):
    """Creates servers in libvirt of localhost
    """

    def sample_config(self):
        return {'lab_id': 'int in range 1-99',
                'username': 'cisco',
                'password': 'cisco123',
                'networks': [41, 61, 42, 43, 62],
                'instances': [{'hostname': 'some name', 'image_url': 'http://path.to.image.file', 'image_checksum': 'checksum', 'on_nets': [41, 62]}]}

    def __init__(self, config):
        import libvirt
        import os
        from lab.Server import Server

        super(ProviderLibvirt, self).__init__(config=config)
        self.lab_id = config['lab_id']
        self.username = config['username']
        self.password = config['password']
        self.network_id = config['networks']
        self.network_names = {x: '{0}-{1}'.format(self.lab_id, x) for x in self.network_id}
        self.instances = config['instances']

        self.dir_for_backing_disks = os.path.abspath(os.path.join('/tmp', 'libvirt', 'backing_images'))
        self.dir_for_main_disks = os.path.abspath(os.path.join('/tmp', 'libvirt', 'main_disks'))
        self.dir_for_saved_xml = os.path.abspath(os.path.join('/tmp', 'libvirt', 'saved_xml'))
        self.domain_tmpl = self.read_config_from_file(config_path='domain_template.txt', directory='libvirt', is_as_string=True)
        self.connection = libvirt.open()
        self.servers = []
        self.local = Server(ip='localhost')

    def delete_lab(self):
        import libvirt

        servers_and_networks = self.connection.listAllDomains()
        servers_and_networks.extend(self.connection.listAllNetworks())
        for obj in servers_and_networks:
            if obj.name().find(str(self.lab_id)) != -1:
                try:
                    obj.destroy()
                except libvirt.libvirtError:
                    pass
                obj.undefine()
        for bridge in self.local.run(command='brctl show | grep 8000 | grep {0} | cut -f1'.format(self.lab_id)).split('\n'):
            if bridge:
                self.local.run('sudo ip l s {0} down && sudo brctl delbr {0}'.format(bridge))
        self.local.run('rm -f {0}/*{1}*'.format(self.dir_for_main_disks, self.lab_id))

    def create_networks(self):
        tmpl = '''
<network>
    <name>{name}</name>
    <bridge name='br{name}' />
    <forward mode="nat"/>
    {ip_part}
</network>
'''
        ip_part4 = '<ip address="10.{lab_id}.0.1" netmask="255.255.255.0"><dhcp><range start="10.{lab_id}.0.2" end="10.{lab_id}.0.254" /></dhcp></ip>'.format(lab_id=self.lab_id)
        ip_part6 = '<ip family="ipv6" address="20{lab_id:02}::1" prefix="64"></ip>'.format(lab_id=self.lab_id)

        for net_id in self.network_id:
            name = self.network_names[net_id]
            xml = tmpl.format(name=name, ip_part=ip_part6 if net_id / 60 else ip_part4)
            self.save_xml(name='net-' + name, xml=xml)
            net = self.connection.networkDefineXML(xml)
            net.create()
            net.setAutostart(True)
            lab_logger.info('Network {0} created'.format(name))

    def save_xml(self, name, xml):
        self.local.put(string_to_put=xml, file_name=name, in_directory=self.dir_for_saved_xml)

    @decorators.repeat_until_not_false(n_repetitions=50, time_between_repetitions=5)
    def ip_for_mac_by_looking_at_libvirt_leases(self, net, mac):
        ans = self.local.run(command='sudo grep "{mac}" /var/lib/libvirt/dnsmasq/{net}.leases'.format(mac=mac, net=net), warn_only=True)
        if ans:
            return ans.split(' ')[2]
        else:
            return ans

    def make_local_file_name(self, where, name, extension):
        import os

        return os.path.abspath(os.path.join(where, str(self.lab_id) + name + '.' + extension))

    def create_cloud_init_disk(self, hostname):
        import uuid

        public_key = self.read_config_from_file(config_path='public', directory='keys', is_as_string=True)

        user_data = self.read_config_from_file(config_path='cloud_init_user_data.txt', directory='libvirt', is_as_string=True)

        user_data = user_data.replace('{username}', self.username)
        user_data = user_data.replace('{password}', self.password)
        user_data = user_data.replace('{public_key}', public_key)

        user_data_path = self.make_local_file_name(where=self.dir_for_main_disks, name=hostname, extension='user_data')
        with open(user_data_path, 'w') as f:
            f.write(user_data)

        meta_data_path = self.make_local_file_name(where=self.dir_for_main_disks, name=hostname, extension='meta_data')
        with open(meta_data_path, 'w') as f:
            meta_data = 'instance_id: {uuid}\nlocal-hostname: {hostname}\n'.format(uuid=uuid.uuid4(), hostname=hostname)
            f.write(meta_data)

        cloud_init_disk_path = self.make_local_file_name(where=self.dir_for_main_disks, name=hostname, extension='cloud_init.qcow2')
        self.local.run('cloud-localds -d qcow2 {ci_d} {u_d} {m_d}'.format(ci_d=cloud_init_disk_path, u_d=user_data_path, m_d=meta_data_path))
        return cloud_init_disk_path

    def create_main_disk(self, hostname, image_url, image_checksum):
        back_disk = self.local.wget_file(url=image_url, checksum=image_checksum, to_directory=self.dir_for_backing_disks)
        main_disk = self.make_local_file_name(where=self.dir_for_main_disks, name=hostname, extension='qcow2')
        self.local.run(command='qemu-img create -f qcow2 -b {0} {1} 15G'.format(back_disk, main_disk), in_directory=self.dir_for_main_disks)

        return main_disk

    def create_server(self, dev_num, hostname, on_nets, image_url, image_checksum):
        from lab.Server import Server

        net_tmpl = '''
<interface type='network'>
    <source network='{{net_name}}'/>
    <mac address='{{mac}}'/>
    <target dev='v{{net_name}}-{hostname}'/>
</interface>

'''.format(lab_id=self.lab_id, dev_num=dev_num, hostname=hostname)

        macs = ['ee:{lab_id:02}:00:{net_id:02}:00:{dev_num:02}'.format(lab_id=self.lab_id, net_id=net_id, dev_num=dev_num) for net_id in on_nets]
        net_names = [self.network_names[net_id] for net_id in on_nets]

        net_part = '\n\n'.join([net_tmpl.format(net_name=net_names[i], mac=macs[i]) for i in range(len(on_nets))])

        disk_part = '''
<disk type='file' device='disk'>
    <driver name='qemu' type='qcow2'/>
    <source file='{main_disk}'/>
    <target dev='vda' bus='virtio'/>
</disk>

<disk type='file' device='disk'>
    <driver name='qemu' type='qcow2'/>
    <source file='{cloud_init_disk}'/>
    <target dev='hdb' bus='ide'/>
</disk>
'''.format(main_disk=self.create_main_disk(hostname=hostname, image_url=image_url, image_checksum=image_checksum), cloud_init_disk=self.create_cloud_init_disk(hostname=hostname))

        xml = self.domain_tmpl.format(hostname='{0}-{1}'.format(self.lab_id, hostname), net_part=net_part, disk_part=disk_part)
        self.save_xml(name=hostname, xml=xml)
        domain = self.connection.defineXML(xml)
        domain.create()

        ip = self.ip_for_mac_by_looking_at_libvirt_leases(net=net_names[0], mac=macs[0])

        lab_logger.info(msg='Domain {0} created'.format(hostname))
        return Server(ip=ip, username=self.username)

    def create_servers(self):
        for server_num, server in enumerate(self.instances, start=1):
            self.servers.append(self.create_server(dev_num=server_num, hostname=server['hostname'], on_nets=server['on_nets'],
                                                   image_url=server['image_url'], image_checksum=server['image_checksum']))
        return self.servers

    def wait_for_servers(self):
        self.delete_lab()
        self.create_networks()
        servers = self.create_servers()
        for server in servers:
            server.hostname = server.run('hostname')
            pwd = server.run('pwd')
            server.run('chmod 755 {0}'.format(pwd))
            if server.run('ip -o link | grep eth1', warn_only=True):
                server.run('sudo ip l s dev eth1 up')
        return servers
