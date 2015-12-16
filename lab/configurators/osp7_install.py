from fabric.api import task


@task
def configure_for_osp7(yaml_path):
    from netaddr import IPNetwork
    import os
    from lab.WithConfig import read_config_from_file
    from lab.providers import ucsm

    lab_config = read_config_from_file(yaml_path=yaml_path)
    osp7_install_template = read_config_from_file(yaml_path='./lab/configs/osp7/osp7-install.yaml', is_as_string=True)
    user_net = IPNetwork(lab_config['nets']['user']['cidr'])
    undercloud_net = IPNetwork(lab_config['nets']['pxe-int']['cidr'])

    # Calculate IPs for user net, VIPs and director IP
    all_nodes_shift = sum([len(x['server-id']) for x in lab_config['nodes'].values()]) + 4
    overcloud_network_cidr = user_net.cidr
    overcloud_external_ip_start = user_net[all_nodes_shift + 1]
    overcloud_external_ip_end = user_net[all_nodes_shift + 2 + len(lab_config['nodes']['control'])]
    overcloud_external_gateway = user_net[1]

    mac_profiles = []
    nodes = []
    counts = {'control': 0, 'ceph': 0, 'compute': 0}
    for ucsm_profile, server in sorted(ucsm.read_config_ssh(yaml_path=yaml_path, is_director=False).iteritems()):
        if 'eth0' in server.ucsm['iface_mac']:
            mac_profiles.append('{0}:{1}'.format(server.ucsm['iface_mac']['eth0'], ucsm_profile))
        pxe_mac = server.ucsm['iface_mac']['pxe-int']

        descriptor = {'"arch"': '"x86_64"', '"cpu"': '"2"', '"memory"': '"8256"', '"disk"': '"1112"',
                      '"name"': '"{0}-{1}"'.format(server.role, counts[server.role]),
                      '"capabilities"':  '"profile:{0},boot_option:local"'.format(server.role),
                      '"mac"': '["{0}"]'.format(pxe_mac),
                      '"pm_type"': '"pxe_ipmitool"',
                      '"pm_addr"': '"{0}"'.format(server.ipmi['ip']),
                      '"pm_user"': '"{0}"'.format(server.ipmi['username']),
                      '"pm_password"': '"{0}"'.format(server.ipmi['password'])}
        counts[server.role] += 1
        nodes.append(',\n\t  '.join(['{0}:{1}'.format(x, y) for x, y in sorted(descriptor.iteritems())]))

    nodes_string = '{{"nodes":[\n\t{{\n\t  {0}\n\t}}\n    ]\n }}'.format('\n\t},\n\t{\n\t  '.join(nodes))

    cfg = osp7_install_template.format(director_node_hostname='g{0}-director.ctocllab.cisco.com'.format(lab_config['lab-id']),
                                       director_node_ssh_ip=user_net[4],
                                       undercloud_network_cidr=undercloud_net,
                                       undercloud_netbits=undercloud_net.prefixlen,
                                       undercloud_local_ip_simple=undercloud_net[1],
                                       undercloud_masquerade_network=undercloud_net,
                                       undercloud_dhcp_start=undercloud_net[100],
                                       undercloud_dhcp_end=undercloud_net[100 + 50],
                                       undercloud_discovery_start=undercloud_net[200],
                                       undercloud_discovery_end=undercloud_net[200 + 50],
                                       undercloud_public_vip=undercloud_net[2],
                                       undercloud_admin_vip=undercloud_net[3],
                                       overcloud_network_cidr=overcloud_network_cidr,
                                       overcloud_external_ip_start=overcloud_external_ip_start,
                                       overcloud_external_gateway=overcloud_external_gateway,
                                       overcloud_external_ip_end=overcloud_external_ip_end,
                                       overcloud_nodes=nodes_string,
                                       overcloud_control_scale=counts['control'],
                                       overcloud_ceph_storage_scale=counts['ceph'],
                                       overcloud_compute_scale=counts['compute'],
                                       ucsm_ip=lab_config['ucsm']['host'],
                                       ucsm_username=lab_config['ucsm']['username'],
                                       ucsm_password=lab_config['ucsm']['password'],
                                       ucsm_mac_profile_list=','.join(mac_profiles),
                                       n9k1_name='n9k-1',
                                       n9k2_name='n9k-2',
                                       overcloud_external_vlan=lab_config['nets']['eth1']['vlan'][1],
                                       n9k1_ip=lab_config['n9k']['host'],
                                       n9k2_ip=lab_config['n9k']['host2'],
                                       n9k_username=lab_config['n9k']['username'],
                                       n9k_password=lab_config['n9k']['password'],
                                       undercloud_lab_pxe_interface='pxe-ext',
                                       undercloud_local_interface='pxe-int',
                                       undercloud_fake_gateway_interface='eth1',
                                       provisioning_nic='nic4',
                                       tenant_nic='nic1',
                                       external_nic='nic2',
                                       cobbler_system='G{0}-DIRECTOR'.format(lab_config['lab-id']))

    folder = 'artefacts'
    file_path = os.path.join(folder, 'g{0}-osp7-install-config.conf'.format(lab_config['lab-id']))
    if not os.path.exists(folder):
        os.makedirs(folder)

    with open(file_path, 'w') as f:
        f.write(cfg)
