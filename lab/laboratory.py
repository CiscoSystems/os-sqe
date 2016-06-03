import tempfile
from lab import with_config


class LaboratoryNetworks(object):
    IPV4 = 'IPv4'
    MAC = 'MAC'

    def __init__(self, cfg):
        from netaddr import IPNetwork

        self._unique_dict = dict()  # to make sure that all needed objects are unique

        self._nets = {}
        self._vlans = {}
        self._ssh_net = None
        self._ipmi_net = None
        self._vlans_to_tor = {}

        for net_name, net_desc in cfg['nets'].items():
            self._nets[net_name] = IPNetwork(net_desc.get('cidr', '1'))
            vlans = net_desc.get('vlan', [])
            self._vlans[net_name] = vlans
            if net_desc.get('is_routable', False):
                self._vlans_to_tor[net_name] = vlans

            if net_desc.get('is_ssh', False):
                self._ssh_net = self._nets[net_name]
            if net_desc.get('is_ipmi', False):
                self._ipmi_net = self._nets[net_name]

    def make_sure_that_object_is_unique(self, type_of_object, obj, node_name):
        """check that given object is valid and unique
        :param type_of_object: IPv4 MAC service-profile
        :param obj: object
        :param node_name: node which tries to register the object
        """
        import validators

        self._unique_dict.setdefault(type_of_object, dict())
        if obj in self._unique_dict[type_of_object].keys():
            raise ValueError('{0} node is trying to use {1}={2} which is already in use by {3}'.format(node_name, type_of_object, obj, self._unique_dict[type_of_object][obj]))
        else:
            if type_of_object == 'MAC':
                is_ok = validators.mac_address(obj)
            elif type_of_object == 'IPv4':
                is_ok = validators.ipv4(str(obj))
            else:
                is_ok = True
            if not is_ok:
                raise ValueError('{0} is not valid {1}'.format(obj, type_of_object))
            self._unique_dict[type_of_object].update({obj: node_name})

    def get_node_credentials(self, node_name, node_description):
        import validators
        import netaddr

        ssh_ip, ssh_username, ssh_password = None, node_description.get('ssh_username'), node_description.get('ssh_password'),
        ipmi_ip, ipmi_username, ipmi_password = None, node_description.get('ipmi_username'), node_description.get('ipmi_password'),

        for ip_type in ['ssh_ip', 'ipmi_ip']:
            ip = node_description.get(ip_type, ssh_ip)
            try:
                index = int(ip)
                if index in [0, 1, 2, 3, -1]:
                    raise ValueError('IP address index {0} is not possible since 0 is network , 1,2,3 are GWs and -1 is broadcast'.format(node_name))
                net = self._get_net_by_name(ip_type)
                try:
                    ip = net[index]
                except (IndexError, ValueError):
                    raise ValueError('index {0} is not in {1}'.format(index, net))
            except ValueError:
                if validators.ipv4(str(ip)):
                    ip = netaddr.IPAddress(ip)
                else:
                    raise ValueError('IP address "{0}" for node "{1}" is invalid'.format(ip, node_name))
            if ip_type == 'ssh_ip':
                ssh_ip = ip
            else:
                ipmi_ip = ip

        self.make_sure_that_object_is_unique(type_of_object=self.IPV4, obj=ssh_ip, node_name=node_name)
        if ipmi_ip != ssh_ip:
            self.make_sure_that_object_is_unique(type_of_object=self.IPV4, obj=ipmi_ip, node_name=node_name)
        return ssh_ip, ssh_username, ssh_password, ipmi_ip, ipmi_username, ipmi_password

    def get_vlans(self, net_name):
        return self._vlans[net_name]

    def get_vlans_to_tor(self):
        return self._vlans_to_tor

    def get_ssh_net(self):
        return self._ssh_net

    def get_ipmi_net(self):
        return self._ipmi_net

    def _get_net_by_name(self, name):
        if 'ssh' in name:
            return self._ssh_net
        elif 'ipmi' in name:
            return self._ipmi_net


class Laboratory(object):
    SUPPORTED_TOPOLOGIES = ['VLAN', 'VXLAN']
    TOPOLOGY_VLAN, TOPOLOGY_VXLAN = SUPPORTED_TOPOLOGIES

    def __repr__(self):
        return self._lab_name

    def __init__(self, config_path):
        from lab.with_config import read_config_from_file

        with open(with_config.KEY_PUBLIC_PATH) as f:
            self.public_key = f.read()
        self._nodes = list()
        self._director = None
        self._cfg = read_config_from_file(yaml_path=config_path)
        self._id = self._cfg['lab-id']
        self._lab_name = self._cfg['lab-name']
        self._is_sriov = self._cfg.get('use-sr-iov', False)

        self._ssh_username, self._ssh_password = self._cfg['cred']['ssh_username'], self._cfg['cred']['ssh_password']
        self._ipmi_username, self._ipmi_password = self._cfg['cred']['ipmi_username'], self._cfg['cred']['ipmi_password']
        self._neutron_username, self._neutron_password = self._cfg['cred']['neutron_username'], self._cfg['cred']['neutron_password']

        self._nets = LaboratoryNetworks(cfg=self._cfg)
        for node_description in self._cfg['nodes']:
            self._process_single_node(node_description)

        if not self._director:
            self._director = self.get_controllers()[0]  # assign first controller as director if no director node specified in yaml config

        for peer in self._cfg['peer-links']:
            pass

    def get_ssh_net(self):
        return self._nets.get_ssh_net()

    def get_ipmi_net(self):
        return self._nets.get_ipmi_net()

    def is_sriov(self):
        return self._is_sriov

    def get_common_ssh_creds(self):
        return self._ssh_username, self._ssh_password

    def _process_single_node(self, node_description):
        from lab.wire import Wire

        own_node = self._create_node(node_description)

        peer_node = None
        for wire in node_description.get('wires', []):  # Example {MLOMl/0: {peer: N9K-C9372PX-ru8-1/26, mac: '00:FE:C8:E4:CD:1D'}}
            try:
                own_port = wire['own-port']
                own_mac = wire['own-mac']
                peer_id = wire['peer-id']
                peer_port = wire['peer-port']
                vlans = wire.get('vlans', [])
                own_nic = wire.get('nic', None)
            except (ValueError, KeyError):
                raise KeyError('you provided {0} as wire description, while expected something like {{own-port: 1/48, peer-id: tor-N9K-C9372PX-ru25, peer-port: 1/46, own-mac: None}}'.format(wire))
            try:
                peer_node = peer_node or self.get_node(peer_id)
            except ValueError:
                raise ValueError('Wire "{0}" specified wrong peer node id: "{1}"'.format(wire, peer_id))
            Wire(node_n=peer_node, port_n=peer_port, node_s=own_node, port_s=own_port, mac_s=own_mac, nic_s=own_nic, vlans=vlans)

    def _create_node(self, node_description):
        from lab.fi import FI, FiServer
        from lab.n9k import Nexus
        from lab.asr import Asr
        from lab.tor import Tor
        from lab.cobbler import CobblerServer
        from lab.cimc import CimcServer
        from lab.vts import Vts, Vtf, Xrvr

        try:
            node_id = node_description['id']
        except KeyError:
            ValueError('id for node "{0}" is not porvided'.format(node_description))

        possible_roles = ['tor', 'terminal', 'cobbler', 'oob', 'pxe',
                          'n9', 'nexus', 'asr', 'fi', 'ucsm', 'vtc', 'xrvr', 'vtf',
                          'director-fi', 'director-n9', 'control-fi', 'control-n9' 'compute-fi', 'compute-n9', 'ceph-fi', 'ceph-n9']
        try:
            role = node_description['role']
        except KeyError:
            raise ValueError(' {0} does not define its role'.format(node_description))

        role = role.lower()
        if role == 'cobbler':
            klass = CobblerServer
        elif role == 'asr':
            klass = Asr
        elif role == 'nexus' or role == 'n9':
            klass = Nexus
        elif role == 'fi' or role == 'ucsm':
            klass = FI
        elif role in ['tor', 'pxe', 'oob', 'terminal']:
            klass = Tor
        elif role in ['director-fi', 'compute-fi', 'control-fi', 'ceph-fi']:
            klass = FiServer
        elif role in ['director-n9', 'compute-n9', 'control-n9', 'ceph-n9']:
            klass = CimcServer
        elif role in ['vtc']:
            klass = Vts
        elif role in ['xrvr']:
            klass = Xrvr
        elif role in ['vtf']:
            klass = Vtf
        else:
            raise ValueError('role "{0}" is not known,  should be one of: {1}'.format(role, possible_roles))

        ssh_ip, ssh_username, ssh_password, ipmi_ip, ipmi_username, ipmi_password = self._nets.get_node_credentials(node_name=node_id, node_description=node_description)
        hostname = node_description.get('hostname', 'NotConfiguredInYaml')

        node = klass(lab=self, name=node_id, role=role, ip=ssh_ip, username=ssh_username or self._ssh_username, password=ssh_password or self._ssh_password, hostname=hostname)
        if 'set_ipmi' in dir(node):
            node.set_ipmi(ip=ipmi_ip, username=ipmi_username or self._ipmi_username, password=ipmi_password or self._ipmi_password)

        # if type(node) is FiServer:
        #     node.set_ucsm_id(port_id)
        # elif type(node) is FI:
        #     node.set_vip(node_description['vip'])
        #     node.set_sriov(self._is_sriov)

        # if type(node) in [FiServer, CimcServer]:
        #     for nic_name in node_description.get('nets', []):
        #         if nic_name in self._cfg['nets']:
        #             mac = self._cfg['nets'][nic_name]['mac-net-part']
        #         else:
        #             raise ValueError('Node "{0}" has NIC name "{1}" which does not match any network'.format(node_id, nic_name))
        #
        #         self._nets.make_sure_that_object_is_unique(type_of_object=LaboratoryNetworks.MAC, obj=nic.get_mac(), node_name=node.name())

        self._nodes.append(node)
        if 'director' in node.role():
            self._director = node
        return node

    def get_id(self):
        return self._id

    def get_nodes(self, klass=None):
        if klass:
            return filter(lambda x: isinstance(x, klass), self._nodes)
        else:
            return self._nodes

    def get_node(self, node_id):
        nodes = list(filter(lambda x: x.name() == node_id, self._nodes))
        if len(nodes) == 1:
            return nodes[0]
        else:
            raise ValueError('Something strange with node_id={0}, list of nodes with this id: {1}'.format(node_id, nodes))

    def get_fi(self):
        from lab.fi import FI

        return self.get_nodes(FI)

    def get_n9(self):
        from lab.n9k import Nexus

        return self.get_nodes(Nexus)

    def get_asr1ks(self):
        from lab.asr import Asr

        return self.get_nodes(Asr)

    def get_cobbler(self):
        return self._get_servers_for_role('cobbler')[0]

    def get_director(self):
        return self._director

    def _get_servers_for_role(self, role):
        return list(filter(lambda x: role in x.role(), self._nodes))

    def get_controllers(self):
        return self._get_servers_for_role('control')

    def get_computes(self):
        return self._get_servers_for_role('compute')

    def get_cimc_servers(self):
        from lab.cimc import CimcServer

        return self.get_nodes(klass=CimcServer)

    def get_all_vlans(self):
        return sorted(set(reduce(lambda l, x: l + (x['vlan']), self._cfg['nets'].values(), [])))

    def get_vlans_to_tor(self):
        return sorted(self._nets.get_vlans_to_tor())

    def get_net_vlans(self, net_name):
        return self._nets.get_vlans(net_name)

    def get_neutron_creds(self):
        return self._neutron_username, self._neutron_password

    def ucsm_nets_with_pxe(self):
        return [x for x in self._cfg['nets'].keys() if 'pxe' in x]

    def vlan_range(self):
        return self._cfg['vlan_range']

    def count_role(self, role_name):
        return len([x for x in self._nodes if role_name in x.role()])

    def logstash_creds(self):
        return self._cfg['logstash']

    def configure_for_osp7(self, topology=TOPOLOGY_VLAN):
        if topology not in self.SUPPORTED_TOPOLOGIES:
            raise ValueError('"{0}" topology is not supported. Correct values: {1}'.format(topology, self.SUPPORTED_TOPOLOGIES))
        self.create_config_file_for_osp7_install(topology)
        self.get_cobbler().configure_for_osp7()
        map(lambda x: x.cleanup(), self.get_n9())
        map(lambda x: x.configure_for_lab(topology), self.get_n9())
        map(lambda x: x.configure_for_osp7(), self.get_cimc_servers())
        map(lambda x: x.configure_for_osp7(topology), self.get_asr1ks())
        self.get_fi()[0].configure_for_osp7()

    def configure_for_mercury(self, topology):
        map(lambda x: x.configure_for_lab(topology), self.get_n9())

    def create_config_file_for_osp7_install(self, topology=TOPOLOGY_VLAN):
        import os
        from lab.logger import lab_logger
        from lab.with_config import read_config_from_file
        from lab.cimc import CimcServer

        lab_logger.info('Creating config for osp7_bootstrap')
        osp7_install_template = read_config_from_file(yaml_path='./configs/osp7/osp7-install.yaml', is_as_string=True)

        # Calculate IPs for user net, VIPs and director IP
        ssh_net = self._nets.get_ssh_net()
        overcloud_network_cidr, overcloud_external_gateway, overcloud_external_ip_start, overcloud_external_ip_end = ssh_net.cidr, ssh_net[1], ssh_net[4+1], ssh_net[-3]

        eth0_mac_versus_service_profile = {}
        overcloud_section = []

        for server in self.get_controllers() + self.get_computes():
            service_profile_name = '""' if isinstance(server, CimcServer) else server.get_ucsm_info()[1]

            try:
                eth0_nic = server.get_nic(nic='eth0')[0]
            except IndexError:
                raise ValueError('{0} has no eth0'.format(server.name()))

            eth0_mac = eth0_nic.get_mac()
            eth0_mac_versus_service_profile[eth0_mac] = service_profile_name

            try:
                pxe_int_nic = server.get_nic(nic='pxe-int')[0]
            except IndexError:
                raise ValueError('{0} has no pxe-int'.format(server.name()))

            pxe_mac = pxe_int_nic.get_mac()
            ipmi_ip, ipmi_username, ipmi_password = server.get_ipmi()
            role = server.name().split('-')[0]
            descriptor = {'"arch"': '"x86_64"', '"cpu"': '"2"', '"memory"': '"8256"', '"disk"': '"1112"',
                          '"name"': '"{0}"'.format(server.name()),
                          '"capabilities"':  '"profile:{0},boot_option:local"'.format(role),
                          '"mac"': '["{0}"]'.format(pxe_mac),
                          '"pm_type"': '"pxe_ipmitool"',
                          '"pm_addr"': '"{0}"'.format(ipmi_ip),
                          '"pm_user"': '"{0}"'.format(ipmi_username),
                          '"pm_password"': '"{0}"'.format(ipmi_password)}
            overcloud_section.append(',\n\t  '.join(['{0}:{1}'.format(x, y) for x, y in sorted(descriptor.iteritems())]))

        network_ucsm_host_list = ','.join(['{0}:{1}'.format(name, mac) for name, mac in eth0_mac_versus_service_profile.iteritems()])

        overcloud_nodes = '{{"nodes":[\n\t{{\n\t  {0}\n\t}}\n    ]\n }}'.format('\n\t},\n\t{\n\t  '.join(overcloud_section))

        nexus_section = []
        switch_tempest_section = []
        for n9 in self.get_n9():
            common_pcs_part = ': {"ports": "port-channel:' + str(n9.get_peer_link_id())  # all pcs n9k-n9k and n9k-fi
            fi_pc_part = ',port-channel:' + ',port-channel:'.join(n9.get_pcs_to_fi())
            mac_port_lines = []
            for server in self.get_controllers() + self.get_computes():
                mac = server.get_nic('pxe-int')[0].get_mac()
                if isinstance(server, CimcServer):
                    individual_ports_part = ','.join([x.get_port_n() for x in server.get_all_wires() if x.get_node_n() == n9])  # add if wired to this n9k only
                    if individual_ports_part:
                        individual_ports_part = ',' + individual_ports_part
                else:
                    individual_ports_part = fi_pc_part
                mac_port_lines.append('"' + mac + '"' + common_pcs_part + individual_ports_part + '" }')

            nexus_servers_section = ',\n\t\t\t\t\t\t'.join(mac_port_lines)

            ssh_ip, ssh_username, ssh_password, hostname = n9.get_ssh()
            switch_tempest_section.append({'hostname': hostname, 'username': ssh_username, 'password': ssh_password, 'sw': str(ssh_ip)})
            n9k_description = ['"' + hostname + '": {',
                               '"ip_address": "' + str(ssh_ip) + '",',
                               '"username": "' + ssh_username + '",',
                               '"password": "' + ssh_password + '",',
                               '"nve_src_intf": 2,',
                               '"ssh_port": 22,',
                               '"physnet": "datacentre",',
                               '"servers": {' + nexus_servers_section + '}}',
                               ]
            nexus_section.append('\n\t\t\t'.join(n9k_description))

        network_nexus_config = '{\n\t\t' + ',\n\t\t'.join(nexus_section) + '}'

        n_controls, n_computes, n_ceph = self.count_role(role_name='control'), self.count_role(role_name='compute'), self.count_role(role_name='ceph')

        director_node_ssh_ip, _, _, director_hostname = self.get_director().get_ssh()

        pxe_int_vlans = self._cfg['nets']['pxe-int']['vlan']
        eth1_vlans = self._cfg['nets']['eth1']['vlan']
        ext_vlan, test_vlan, stor_vlan, stor_mgmt_vlan, tenant_vlan, fip_vlan = eth1_vlans[1], pxe_int_vlans[1], pxe_int_vlans[2], pxe_int_vlans[3], pxe_int_vlans[4], eth1_vlans[0]

        ucsm_vip = self.get_fi()[0].get_vip()

        cfg = osp7_install_template.format(director_node_hostname=director_hostname, director_node_ssh_ip=director_node_ssh_ip,

                                           ext_vlan=ext_vlan, test_vlan=test_vlan, stor_vlan=stor_vlan, stor_mgmt_vlan=stor_mgmt_vlan, tenant_vlan=tenant_vlan, fip_vlan=fip_vlan,
                                           vlan_range=self.vlan_range(),

                                           overcloud_network_cidr=overcloud_network_cidr, overcloud_external_ip_start=overcloud_external_ip_start, overcloud_external_gateway=overcloud_external_gateway,
                                           overcloud_external_ip_end=overcloud_external_ip_end,

                                           overcloud_nodes=overcloud_nodes,

                                           overcloud_control_scale=n_controls, overcloud_ceph_storage_scale=n_ceph, overcloud_compute_scale=n_computes,

                                           network_ucsm_ip=ucsm_vip, network_ucsm_username=self._neutron_username, network_ucsm_password=self._neutron_password, network_ucsm_host_list=network_ucsm_host_list,

                                           undercloud_lab_pxe_interface='pxe-ext', undercloud_local_interface='pxe-int', undercloud_fake_gateway_interface='eth1',

                                           provisioning_nic='nic4', tenant_nic='nic1', external_nic='nic2',

                                           cobbler_system='G{0}-DIRECTOR'.format(self._id),

                                           network_nexus_config=network_nexus_config,

                                           switch_tempest_section=switch_tempest_section,
                                           do_sriov=self._is_sriov
                                           )

        if topology == self.TOPOLOGY_VXLAN:
            pass

        folder = 'artifacts'
        file_path = os.path.join(folder, 'g{0}-osp7-install-config.conf'.format(self._id))
        if not os.path.exists(folder):
            os.makedirs(folder)

        with open(file_path, 'w') as f:
            f.write(cfg)
        lab_logger.info('finished. Execute osp7_bootstrap --config {0}'.format(file_path))
