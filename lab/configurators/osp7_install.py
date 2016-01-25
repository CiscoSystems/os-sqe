def configure_for_osp7(yaml_path):
    import os
    from lab.laboratory import Laboratory
    from lab.with_config import read_config_from_file
    from lab.logger import lab_logger

    lab_logger.info('Creating config for osp7_bootstrap')
    lab = Laboratory(config_path=yaml_path)
    osp7_install_template = read_config_from_file(yaml_path='./configs/osp7/osp7-install.yaml', is_as_string=True)

    # Calculate IPs for user net, VIPs and director IP
    overcloud_network_cidr = lab.user_net_cidr()
    overcloud_external_ip_start, overcloud_external_ip_end = lab.user_net_free_range()
    overcloud_external_gateway = lab.user_gw

    mac_profiles = []
    nodes = []
    for server in lab.all_but_director():
        mac_profiles.append('{0}:{1}'.format(server.nic_mac(nic_name='eth0'), server.ucsm_profile()))
        pxe_mac = server.nic_mac(nic_name='pxe-int')
        ipmi_ip, ipmi_username, ipmi_password = server.ipmi_creds()
        descriptor = {'"arch"': '"x86_64"', '"cpu"': '"2"', '"memory"': '"8256"', '"disk"': '"1112"',
                      '"name"': '"{0}"'.format(server.name()),
                      '"capabilities"':  '"profile:{0},boot_option:local"'.format(server.role),
                      '"mac"': '["{0}"]'.format(pxe_mac),
                      '"pm_type"': '"pxe_ipmitool"',
                      '"pm_addr"': '"{0}"'.format(ipmi_ip),
                      '"pm_user"': '"{0}"'.format(ipmi_username),
                      '"pm_password"': '"{0}"'.format(ipmi_password)}
        nodes.append(',\n\t  '.join(['{0}:{1}'.format(x, y) for x, y in sorted(descriptor.iteritems())]))

    nodes_string = '{{"nodes":[\n\t{{\n\t  {0}\n\t}}\n    ]\n }}'.format('\n\t},\n\t{\n\t  '.join(nodes))

    n9k1_ip, n9k2_ip, n9k_username, n9k_password = lab.n9k_creds()
    ucsm_ip, ucsm_username, ucsm_password = lab.ucsm_creds()
    cfg = osp7_install_template.format(director_node_hostname=lab.director().hostname,
                                       director_node_ssh_ip=lab.director().ip,
                                       overcloud_network_cidr=overcloud_network_cidr,
                                       overcloud_external_ip_start=overcloud_external_ip_start,
                                       overcloud_external_gateway=overcloud_external_gateway,
                                       overcloud_external_ip_end=overcloud_external_ip_end,
                                       overcloud_nodes=nodes_string,
                                       overcloud_control_scale=lab.count_role(role_name='control'),
                                       overcloud_ceph_storage_scale=lab.count_role(role_name='ceph'),
                                       overcloud_compute_scale=lab.count_role(role_name='compute'),
                                       ucsm_ip=ucsm_ip,
                                       ucsm_username=ucsm_username,
                                       ucsm_password=ucsm_password,
                                       ucsm_mac_profile_list=','.join(mac_profiles),
                                       n9k1_name='n9k-1',
                                       n9k2_name='n9k-2',
                                       overcloud_external_vlan=lab.external_vlan(),
                                       n9k1_ip=n9k1_ip,
                                       n9k2_ip=n9k2_ip,
                                       n9k_username=n9k_username,
                                       n9k_password=n9k_password,
                                       undercloud_lab_pxe_interface='pxe-ext',
                                       undercloud_local_interface='pxe-int',
                                       undercloud_fake_gateway_interface='eth1',
                                       provisioning_nic='nic4',
                                       tenant_nic='nic1',
                                       external_nic='nic2',
                                       cobbler_system='G{0}-DIRECTOR'.format(lab.id),
                                       controller0_eth0_mac=lab.controllers()[0].nics[0][1],
                                       controller1_eth0_mac=lab.controllers()[1].nics[0][1],
                                       controller2_eth0_mac=lab.controllers()[2].nics[0][1])

    folder = 'artefacts'
    file_path = os.path.join(folder, 'g{0}-osp7-install-config.conf'.format(lab.id))
    if not os.path.exists(folder):
        os.makedirs(folder)

    with open(file_path, 'w') as f:
        f.write(cfg)
    lab_logger.info('finished. Execute osp7_bootstrap --config {0}'.format(file_path))
