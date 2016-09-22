class WithMercuryMixIn(object):

    def create_mercury_setup_data_yaml(self, is_add_vts_role):
        from lab import with_config

        build_node = getattr(self, 'get_director')()

        installer_config_template = with_config.read_config_from_file(config_path='mercury.template', directory='mercury', is_as_string=True)

        lab = build_node.lab()
        bld_ip_oob, bld_username_oob, bld_password_oob = build_node.get_oob()
        bld_ip_api, bld_username_api, bld_password_api = build_node.get_ssh()
        dns_ip = build_node.lab().get_dns()[0]

        a_net, t_net, m_net, e_net = lab.get_all_nets()['a'], lab.get_all_nets()['t'], lab.get_all_nets()['mx'], lab.get_all_nets()['e']

        lb_ip_a = a_net.get_ip_for_index(10)
        lb_ip_m = m_net.get_ip_for_index(138)
        lab.make_sure_that_object_is_unique(str(lb_ip_a), 'MERCURY')
        lab.make_sure_that_object_is_unique(str(lb_ip_m), 'MERCURY')

        a_cidr, a_vlan, a_gw = a_net.get_cidr(), a_net.get_vlan(), a_net.get_gw()
        t_cidr, t_vlan, t_gw = t_net.get_cidr(), t_net.get_vlan(), t_net.get_gw()
        m_cidr, m_vlan, m_gw = m_net.get_cidr(), m_net.get_vlan(), m_net.get_gw()
        e_vlan = e_net.get_vlan()

        m_pool = '{} to {}'.format(m_net.get_ip_for_index(10), m_net.get_ip_for_index(50))
        t_pool = '{} to {}'.format(t_net.get_ip_for_index(10), t_net.get_ip_for_index(50))

        vtc = lab.get_node_by_id('vtc1')
        vtc_mx_ip = vtc.get_vtc_vips()[1]
        _, vtc_username, vtc_password = vtc.get_oob()

        controllers_part = '\n     - '.join(map(lambda x: x.get_hostname(), lab.get_controllers()))
        computes_part = '\n     - '.join(map(lambda x: x.get_hostname(), lab.get_computes()))
        vts_hosts_part = '\n     - '.join(map(lambda x: x.get_hostname(), lab.get_vts_hosts()))

        roles_part = '   control:\n     - {}\n   compute:\n     - {}\n'.format(controllers_part, computes_part)
        if is_add_vts_role:
            roles_part += '   vts:\n     - {}\n'.format(vts_hosts_part)

        servers_part = ''
        nodes = lab.get_controllers() + lab.get_computes()
        if is_add_vts_role:
            nodes += lab.get_vts_hosts()

        for node in nodes:
            oob_ip, oob_username, oob_password = node.get_oob()
            ip_mx = node.get_ip_mx()
            ru = node.get_hardware_info()[0]
            servers_part += '   {nm}:\n       cimc_info: {{"cimc_ip" : "{ip}", "cimc_password" : "{p}"}}\n       rack_info: {{"rack_id": "{ru}"}}\n       management_ip: {ip_mx}\n\n'.format(nm=node.get_hostname(),
                                                                                                                                                                                             p=oob_password, ip=oob_ip, ru=ru,
                                                                                                                                                                                             ip_mx=ip_mx)

        installer_config_body = installer_config_template.format(common_username_oob=bld_username_oob, common_password_oob=bld_password_api, dns_ip=dns_ip, vts_kickstart=' vts: control-sda-c220m4.ks' if is_add_vts_role else '',
                                                                 cidr_a=a_cidr, vlan_a=a_vlan, gw_a=a_gw,
                                                                 cidr_m=m_cidr, vlan_m=m_vlan, gw_m=m_gw, pool_m=m_pool, bld_ip_m=build_node.get_ip_mx(),
                                                                 cidr_t=t_cidr, vlan_t=t_vlan, gw_t=t_gw, pool_t=t_pool,
                                                                 vlan_e=e_vlan,
                                                                 roles_part=roles_part, servers_part=servers_part,
                                                                 lb_ip_a=lb_ip_a, lb_ip_m=lb_ip_m,
                                                                 vtc_mx_vip=vtc_mx_ip, vtc_username=vtc_username, vtc_password=vtc_password, common_ssh_username=bld_username_api,
                                                                 bld_ip_oob=bld_ip_oob, bld_username_oob=bld_username_oob, bld_password_oob=bld_password_oob,
                                                                 bld_ip_a_with_prefix=build_node.get_ip_api_with_prefix(), bld_ip_m_with_prefix=build_node.get_ip_mx_with_prefix())

        with with_config.open_artifact('setup_data.yaml', 'w') as f:
            f.write(installer_config_body)

        return installer_config_body
