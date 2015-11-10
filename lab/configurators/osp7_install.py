from fabric.api import task


@task
def configure_for_osp7(yaml_path):
    from netaddr import IPNetwork
    from lab.WithConfig import read_config_from_file
    from lab.providers import ucsm

    lab_config = read_config_from_file(yaml_path=yaml_path)
    osp7_install_template = read_config_from_file(yaml_path='./lab/configs/osp7/osp7-install.yaml', is_as_string=True)
    user_net = IPNetwork(lab_config['user-net']['cidr'])
    undercloud_net = IPNetwork(lab_config['pxe-int-net']['cidr'])

    mac_profiles = []
    nodes = []
    for ucsm_profile, server in sorted(ucsm.read_config_ssh(yaml_path=yaml_path, is_director=False).iteritems()):
        mac_profiles.append('{0}:{1}'.format(server.ucsm['iface_mac']['eth0'], ucsm_profile))
        pxe_mac = server.ucsm['iface_mac']['pxe-int']

        descriptor = {'arch': 'x86_64', 'cpu': '2', 'memory': '256', 'disk': '1112',
                      'mac': '[{0}]'.format(pxe_mac),
                      'pm_type': 'pxe_ipmitool', 'pm_addr': server.ipmi['ip'], 'pm_user': server.ipmi['username'], 'pm_password': server.ipmi['password']}

        nodes.append(',\n\t  '.join(['"{0}":"{1}"'.format(x, y) for x, y in sorted(descriptor.iteritems())]))

    nodes_string = '{{"nodes":[\n\t{{\n\t  {0}\n\t}}\n\t]\n\t}}'.format('\n\t},\n\t{\n\t  '.join(nodes))

    cfg = osp7_install_template.format(director_node_hostname='g{0}-director.ctocllab.cisco.com'.format(lab_config['lab-id']),
                                       director_node_ssh_ip=user_net[4],
                                       undercloud_network_cidr=undercloud_net,
                                       undercloud_local_ip=undercloud_net[1],
                                       undercloud_local_ip_simple=undercloud_net[1],
                                       undercloud_local_interface=lab_config['pxe-int-net']['iface-name'],
                                       undercloud_masquerade_network=undercloud_net,
                                       undercloud_dhcp_start=undercloud_net[100],
                                       undercloud_dhcp_end=undercloud_net[100 + 50],
                                       undercloud_network_gateway=undercloud_net[1],
                                       undercloud_discovery_start=undercloud_net[200],
                                       undercloud_discovery_end=undercloud_net[200 + 50],
                                       undercloud_public_vip=undercloud_net[3],
                                       undercloud_admin_vip=undercloud_net[4],
                                       overcloud_nodes=nodes_string,
                                       overcloud_compute_scale=len(mac_profiles) - 3,
                                       ucsm_ip=lab_config['ucsm']['host'],
                                       ucsm_username=lab_config['ucsm']['username'],
                                       ucsm_password=lab_config['ucsm']['password'],
                                       ucsm_mac_profile_list=','.join(mac_profiles),
                                       cobbler_system=lab_config['ucsm']['director-profile'])

    with open('osp7_install_config.conf', 'w') as f:
        f.write(cfg)
