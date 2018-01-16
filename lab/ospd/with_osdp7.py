class WithOspd7(object):
    SUPPORTED_TOPOLOGIES = ['VLAN', 'VXLAN']
    TOPOLOGY_VLAN, TOPOLOGY_VXLAN = SUPPORTED_TOPOLOGIES

    def configure_for_osp7(self, topology=TOPOLOGY_VLAN):
        from lab.nodes.fi import FI
        from lab.nodes.asr import Asr
        from lab.nodes.cobbler import CobblerServer

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
        from lab.nodes.cimc_server import CimcServer
        from lab.nodes.fi import FI
        from lab.nodes.n9 import N9

        lab_logger.info('Creating config for osp7_bootstrap')
        osp7_install_template = read_config_from_file(config_path='./configs/osp7/osp7-install.yaml', is_as_string=True)

        # Calculate IPs for user net, VIPs and director IP
        ssh_net = filter(lambda net: net.is_ssh(), self._nets.values())[0]
        overcloud_network_cidr, overcloud_external_gateway, overcloud_external_ip_start, overcloud_external_ip_end = ssh_net.cidr, ssh_net[1], ssh_net[4 + 1], ssh_net[-3]

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
                          '"capabilities"': '"profile:{0},boot_option:local"'.format(role),
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
        for n9 in self.get_nodes_by_class(N9):
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

            ip, username, password, hostname = n9.get_ssh()
            switch_tempest_section.append({'hostname': hostname, 'username': username, 'password': password, 'sw': str(ip)})
            n9k_description = ['"' + hostname + '": {',
                               '"ip_address": "' + str(ip) + '",',
                               '"username": "' + username + '",',
                               '"password": "' + password + '",',
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
