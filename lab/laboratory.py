class Laboratory(object):
    SUPPORTED_LAB_TYPES = ['MERCURY', 'OSPD']
    LAB_MERCURY, LAB_OSPD = SUPPORTED_LAB_TYPES
    SUPPORTED_TOPOLOGIES = ['VLAN', 'VXLAN']
    TOPOLOGY_VLAN, TOPOLOGY_VXLAN = SUPPORTED_TOPOLOGIES

    def __repr__(self):
        return self._lab_name

    def __init__(self, config_path):
        from lab import with_config
        from lab.network import Network

        self._cfg = with_config.read_config_from_file(config_path=config_path)
        self._id = self._cfg['lab-id']
        self._lab_name = self._cfg['lab-name']
        self._lab_type = self._cfg['lab-type']
        if self._lab_type not in self.SUPPORTED_LAB_TYPES:
            raise ValueError('"{}" is not one of supported types: {}'.format(self._lab_type, self.SUPPORTED_LAB_TYPES))

        self._unique_dict = dict()  # to make sure that all needed objects are unique
        self._nodes = list()
        self._director = None
        self._is_sriov = self._cfg.get('use-sr-iov', False)

        self._dns, self._ntp = self._cfg['dns'], self._cfg['ntp']
        self._neutron_username, self._neutron_password = self._cfg['special-creds']['neutron_username'], self._cfg['special-creds']['neutron_password']

        self._nets = {}

        net_markers_used = []
        for net_name, net_desc in self._cfg['nets'].items():
            try:
                net = Network(name=net_name, cidr=net_desc['cidr'], mac_pattern=net_desc['mac-pattern'], vlan=str(net_desc['vlan']))
                self._nets[net_name] = net
                if net_desc.get('is-via-tor', False):
                    net.set_is_via_tor()
                for is_xxx in ['pxe', 'ssh', 'vts']:
                    if net_desc.get('is-' + is_xxx, False):
                        if is_xxx not in net_markers_used:
                            getattr(net, 'set_is_' + is_xxx)()  # will set marker to True
                            net_markers_used.append(is_xxx)
                        else:
                            raise ValueError('Check net section- more then one network is marked as is-' + is_xxx)

            except KeyError as ex:
                raise ValueError('Network "{}" has no {}'.format(net_name, ex.message))

        for node_description in self._cfg['nodes']:
            self._process_single_node(node_description)

        if not self._director:
            self._director = self.get_controllers()[0]  # assign first controller as director if no director node specified in yaml config

        for peer_link in self._cfg['peer-links']:  # list of {'own-id': 'n97', 'own-port': '1/46', 'port-channel': 'pc100', 'peer-id': 'n98', 'peer-port': '1/46'}
            own_node = self.get_node_by_id(peer_link['own-id'])
            self._process_single_wire(own_node=own_node, wire_info=(peer_link['own-port'], {'peer-id': peer_link['peer-id'], 'peer-port': peer_link['peer-port'], 'port-channel': peer_link['port-channel']}))

    def is_sriov(self):
        return self._is_sriov

    def get_all_nets(self):
        return self._nets

    def _process_single_node(self, node_description):
        own_node = self._create_node(node_description)
        all_wires_of_node = node_description.get('wires', {})

        all_nics_of_node = []  # We need to collect all vlans (1 per NIC) to assign them to wires on which this NIC sits
        for nic_name, ip_ports in node_description.get('nics', {}).items():  # {api: {ip: 10.23.221.184, port: pc26}, mx: {...}, ...}
            nic_on_net = self._nets[nic_name]  # NIC name coincides with network name on which it sits
            nic_ip_or_index = ip_ports.get('ip')
            nic_on_port_or_port_channel = ip_ports['port']
            # nic port might be physical port like LOM0 or port channel like pc40, wires contains a list of physical ports, some with port-channel attribute
            if nic_on_port_or_port_channel in all_wires_of_node:  # it's  a physical port
                nic_on_phys_port = nic_on_port_or_port_channel
                nic_mac_or_pattern = all_wires_of_node[nic_on_phys_port].get('own-mac', nic_on_net.get_mac_pattern())  # id mac specified in wires section - use it, else construct mac for this network
                nic_on_these_phys_port_ids = [nic_on_phys_port]  # this NIC sits on a single physical wire
            else:  # this nic sits on port channel, find all wires which form this port channel
                nic_on_port_channel = nic_on_port_or_port_channel
                nic_on_these_phys_port_ids = [x[0] for x in all_wires_of_node.items() if x[1].get('port-channel') == nic_on_port_channel]
                if len(nic_on_these_phys_port_ids) == 0:
                    raise ValueError('{}: NIC "{}" tries to sit on port channel "{}" which does not exist'.format(own_node, nic_name, nic_on_port_channel))
                nic_mac_or_pattern = nic_on_net.get_mac_pattern()  # always use MAC pattern for port channels

            for port_id in nic_on_these_phys_port_ids:  # add vlan of this NIC to all wires concerned
                all_wires_of_node[port_id].setdefault('vlans', [])
                all_wires_of_node[port_id]['vlans'].append(nic_on_net.get_vlan())

            all_nics_of_node.append({'name': nic_name, 'mac-or-pattern': nic_mac_or_pattern, 'ip-or-index': nic_ip_or_index, 'net': nic_on_net, 'own-ports': nic_on_these_phys_port_ids})

        for wire_info in all_wires_of_node.items():  # now all vlans for wires collected, create wires and interconnect nodes by them
            self._process_single_wire(own_node=own_node, wire_info=wire_info)

        # now all wires are created and all peers of this node are connected
        for nic_info in all_nics_of_node:  # {'name': name, 'mac-or_pattern': mac, 'ip-or-index': ip, 'net': obj_of_Network, own-ports: [phys_port1, phys_port2]}
            nic_on_these_wires = filter(lambda y: y.get_own_port(own_node) in nic_info['own-ports'], own_node.get_all_wires())  # find all wires, this NIC sits on
            own_node.add_nic(nic_name=nic_info['name'], mac_or_pattern=nic_info['mac-or-pattern'], ip_or_index=nic_info['ip-or-index'], net=nic_info['net'], on_wires=nic_on_these_wires)

    @staticmethod
    def _check_port_id_correctness(klass, port_id):  # correct values MGMT, LOM-1 LOM-2 MLOM-1/0 MLOM-1/1 1/25
        from lab.cimc import CimcServer
        from lab.n9k import Nexus
        from lab.fi import FI, FiServer

        possible_mlom = ['MLOM-0/0', 'MLOM-0/1']
        possible_lom = ['LOM-1', 'LOM-2']

        if 'MGMT' in port_id:
            if port_id != 'MGMT':
                raise ValueError('Port id "{}" is wrong, the only possible value is MGMT'.format(port_id))
            return

        if klass is CimcServer:
            if 'MLOM' in port_id:
                if port_id not in possible_mlom:
                    raise ValueError('Ucs connected to N9K port id "{}" is wrong, possible MLOM port ids are "{}"'.format(port_id, possible_mlom))
                return
            if 'LOM' in port_id:
                if port_id not in possible_lom:
                    raise ValueError('Ucs connected to N9K port id "{}" is wrong, possible LOM port ids are "{}"'.format(port_id, possible_lom))
                return
        if klass in [Nexus, FI]:
            if port_id.count('/') != 1:
                raise ValueError('N9K or FI port id "{}" is wrong, it should contain single "/"'.format(port_id))
            for value in port_id.split('/'):
                try:
                    int(value)
                except ValueError:
                    raise ValueError('N9K or FI port id "{}" is wrong, it have to be <number>/<number>'.format(port_id))
        if klass is FiServer:
            left, right = port_id.rsplit('/', 1)
            if right not in ['a', 'b']:
                raise ValueError('UCS connected to FI port id "{}" is wrong, it have to be finished by "/a" or "/b"'.format(port_id))

            for value in left.split('/'):
                try:
                    int(value)
                except ValueError:
                    raise ValueError('UCS connected to FI port id "{}" is wrong, have to be "<number>" or "<number>/<number>" before "/a" or "/b"'.format(port_id))

    def _process_single_wire(self, own_node, wire_info):  # Example {MLOMl/0: {peer-id: n98,  peer-port: 1/30, own-mac: '00:FE:C8:E4:B4:CE', port-channel: pc20, vlans: [3, 4]}
        from lab.wire import Wire

        own_port_id, peer_info = wire_info
        own_port_id = own_port_id.upper()
        self._check_port_id_correctness(klass=type(own_node), port_id=own_port_id)
        try:
            peer_node_id = peer_info['peer-id']
            peer_port_id = peer_info['peer-port']
        except KeyError as ex:
            raise ValueError('Node "{}": port "{}" has no "{}"'.format(own_node.get_id(), own_port_id, ex.message))

        try:
            peer_node = self.get_node_by_id(peer_node_id)
        except ValueError:
            if peer_node_id in ['None', 'none']:  # this port is not connected
                return
            raise ValueError('Node "{}": specified wrong peer node id: "{}"'.format(own_node.get_id(), peer_node_id))

        self._check_port_id_correctness(klass=type(peer_node), port_id=peer_port_id)
        self.make_sure_that_object_is_unique(obj='{}-{}'.format(peer_node.get_id(), peer_port_id), node_id=own_node.get_id())  # check that this peer_node-peer_port is unique
        port_channel = peer_info.get('port-channel')

        vlans = peer_info.get('vlans', [])
        Wire(node_n=peer_node, port_n=peer_port_id, node_s=own_node, port_s=own_port_id, port_channel=port_channel, vlans=vlans)

    @staticmethod
    def _get_role_class(role):
        from lab.fi import FI, FiDirector, FiController, FiCompute, FiCeph
        from lab.n9k import Nexus
        from lab.asr import Asr
        from lab.tor import Tor, Oob, Pxe, Terminal
        from lab.cobbler import CobblerServer
        from lab.cimc import CimcDirector, CimcController, CimcCompute, CimcCeph
        from lab.vts_classes.xrvr import Xrvr
        from lab.vts_classes.vtf import Vtf
        from lab.vts_classes.vtc import VtsHost
        from lab.vts_classes.vtc import Vtc

        role = role.lower()
        roles = {Oob.ROLE: Oob, Pxe.ROLE: Pxe, Tor.ROLE: Tor, Terminal.ROLE: Terminal, CobblerServer.ROLE: CobblerServer,
                 Asr.ROLE: Asr, Nexus.ROLE: Nexus, FI.ROLE: FI,
                 FiDirector.ROLE: FiDirector, FiController.ROLE: FiController, FiCompute.ROLE: FiCompute, FiCeph.ROLE: FiCeph,
                 CimcDirector.ROLE: CimcDirector, CimcController.ROLE: CimcController, CimcCompute.ROLE: CimcCompute, CimcCeph.ROLE: CimcCeph,
                 VtsHost.ROLE: VtsHost, Vtc.ROLE: Vtc, Xrvr.ROLE: Xrvr, Vtf.ROLE: Vtf}

        try:
            return roles[role]
        except KeyError:
            raise ValueError('role "{0}" is not known,  should be one of: {1}'.format(role, roles.keys()))

    def _create_node(self, node_description):
        try:
            node_id = node_description['id']
            role = node_description['role']

            klass = self._get_role_class(role)
            node = klass(lab=self, node_id=node_id, role=role, hostname=node_description.get('hostname', '{}-{}.ctocllab.cisco.com'.format(self, node_id)))

            try:
                node.set_oob_creds(ip=node_description['oob-ip'], username=node_description['oob-username'], password=node_description['oob-password'])
                node.set_ssh_creds(username=node_description['ssh-username'], password=node_description['ssh-password'])
            except KeyError as ex:
                raise ValueError('Node "{}": has no "{}"'.format(node_id, ex.message))

            if 'set_ucsm_id' in dir(node):
                node.set_ucsm_id(node_description['ucsm-id'])
            if 'set_vip' in dir(node):
                node.set_vip(node_description['vip'])
            if 'set_sriov' in dir(node):
                node.set_sriov(self._is_sriov)
            if 'director' in node.get_role():
                self._director = node
            node.set_hardware_info(ru=node_description.get('ru', 'Default in Laboratory._create_node()'), model=node_description.get('model', 'Default in Laboratory._create_node()'))
            self._nodes.append(node)
            return node
        except KeyError as ex:
            ValueError('"{}" for node "{}" is not provided'.format(ex.message, node_description))

    def get_id(self):
        return self._id

    def get_nodes_by_class(self, klass=None):
        if klass:
            classes = klass if type(klass) is list else [klass]
            nodes = []
            for klass in classes:
                nodes += filter(lambda x: isinstance(x, klass), self._nodes)
            return nodes
        else:
            return self._nodes

    def get_node_by_id(self, node_id):
        nodes = list(filter(lambda x: x.get_id() == node_id, self._nodes))
        if len(nodes) == 1:
            return nodes[0]
        else:
            raise ValueError('Something strange with node_id={0}, list of nodes with this id: {1}'.format(node_id, nodes))

    def get_director(self):
        return self._director

    def get_controllers(self):
        from lab.cimc import CimcController
        from lab.fi import FiController

        return filter(lambda x: type(x) in [CimcController, FiController], self._nodes)

    def get_computes(self):
        from lab.cimc import CimcCompute
        from lab.fi import FiCompute

        return filter(lambda x: type(x) in [CimcCompute, FiCompute], self._nodes)

    def get_cimc_servers(self):
        from lab.cimc import CimcServer

        return self.get_nodes_by_class(klass=CimcServer)

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
        from lab.fi import FI
        from lab.asr import Asr
        from lab.cobbler import CobblerServer

        if topology not in self.SUPPORTED_TOPOLOGIES:
            raise ValueError('"{0}" topology is not supported. Correct values: {1}'.format(topology, self.SUPPORTED_TOPOLOGIES))
        self.create_config_file_for_osp7_install(topology)
        self.get_nodes_by_class(CobblerServer)[0].cobbler_deploy()
        self.n9_configure(is_clean_before=True)
        map(lambda x: x.configure_for_osp7(), self.get_cimc_servers())
        map(lambda x: x.configure_for_osp7(topology), self.get_nodes_by_class(Asr))
        self.get_nodes_by_class(FI)[0].configure_for_osp7()

    def create_config_file_for_osp7_install(self, topology=TOPOLOGY_VLAN):
        import os
        from lab.logger import lab_logger
        from lab.with_config import read_config_from_file
        from lab.cimc import CimcServer
        from lab.fi import FI
        from lab.n9k import Nexus

        lab_logger.info('Creating config for osp7_bootstrap')
        osp7_install_template = read_config_from_file(config_path='./configs/osp7/osp7-install.yaml', is_as_string=True)

        # Calculate IPs for user net, VIPs and director IP
        ssh_net = filter(lambda net: net.is_ssh(), self._nets.values())[0]
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
            overcloud_section.append(',\n\t  '.join(['{0}:{1}'.format(x, y) for x, y in sorted(descriptor.items())]))

        network_ucsm_host_list = ','.join(['{0}:{1}'.format(name, mac) for name, mac in eth0_mac_versus_service_profile.items()])

        overcloud_nodes = '{{"nodes":[\n\t{{\n\t  {0}\n\t}}\n    ]\n }}'.format('\n\t},\n\t{\n\t  '.join(overcloud_section))

        nexus_section = []
        switch_tempest_section = []
        for n9 in self.get_nodes_by_class(Nexus):
            common_pcs_part = ': {"ports": "port-channel:' + str(n9.get_peer_link_id())  # all pcs n9k-n9k and n9k-fi
            fi_pc_part = ',port-channel:' + ',port-channel:'.join(n9.get_pcs_to_fi())
            mac_port_lines = []
            for server in self.get_controllers() + self.get_computes():
                mac = server.get_nic('pxe-int')[0].get_mac()
                if isinstance(server, CimcServer):
                    individual_ports_part = ','.join([x.get_peer_node(server) for x in server.get_all_wires() if x.get_peer_node(server) == n9])  # add if wired to this n9k only
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

        ucsm_vip = self.get_nodes_by_class(FI)[0].get_ucsm_vip()

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

    def make_sure_that_object_is_unique(self, obj, node_id):
        """check that given object is unique
        :param obj: object
        :param node_id: node which tries to register the object
        """

        if str(obj) in self._unique_dict.keys():
            raise ValueError('{} node tries to own {} which is already in use by {}'.format(node_id, obj, self._unique_dict[obj]))
        else:
            self._unique_dict[str(obj)] = node_id

    def get_type(self):
        return self._lab_type

    def get_dns(self):
        return self._dns

    def get_ntp(self):
        return self._ntp

    def n9_configure(self, is_clean_before=False):
        from lab.n9k import Nexus

        list_of_n9k = self.get_nodes_by_class(Nexus)
        if is_clean_before:
            map(lambda x: x.n9_cleanup(), list_of_n9k)
        map(lambda x: x.n9_configure_for_lab(), list_of_n9k)
