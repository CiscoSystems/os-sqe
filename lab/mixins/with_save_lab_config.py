class WithSaveLabConfigMixin(object):
    def save_self_config(self):
        from lab.nodes.virtual_server import VirtualServer
        from lab.nodes.vtc import Vtc

        virtual = 'V'
        switch = 'S'
        others = 'O'

        def net_yaml_body(net):
            return '  {{net-id: {:3}, vlan: {:4}, cidr: {:19}, is-via-tor: {:5}, should-be: {}}}'.format(net.get_net_id(), net.get_vlan_id(), net.get_cidr(), 'True' if net.is_via_tor() else 'False', net.get_roles())

        def nic_yaml_body(nic):
            return '{{nic-id: {:3}, ip: {:20}, is-ssh: {} }}'.format(nic.get_nic_id(), nic.get_ip_and_mask()[0], nic.is_ssh())
    
        def node_yaml_body(node, tp):
            n_id = node.get_node_id()
            pn_id = node.get_proxy_node_id()
            role = node.get_role()
            oob_ip, oob_u, oob_p = node.get_oob()
            if tp == switch:
                ssh_u, ssh_p = oob_u, oob_p
            else:
                ssh_u, ssh_p = node.get_ssh_u_p()
            a = ' {{node-id: {:5}, role: {:10}, proxy-id: {:5}, ssh-username: {:15}, ssh-password: {:9}, oob-ip: {:15},  oob-username: {:15}, oob-password: {:9}'.format(n_id, role, pn_id, ssh_u, ssh_p, oob_ip, oob_u, oob_p)
            if tp == switch:
                a += ', hostname: {:23}'.format(node.get_hostname())
            if tp == virtual:
                a += ', virtual-on: {:5}'.format(node.get_hard_node_id())
            if type(node) is Vtc:
                vip_a, vip_m = node.get_vtc_vips()
                a += ', vip_a: {:15}, vip_m: {:15}'.format(vip_a, vip_m)
            if tp != virtual:
                a += ', model: {:15}, ru: {:4}'.format(node.get_model(), node.get_ru())
            if tp != switch:
                nics = ',\n              '.join(map(lambda x: nic_yaml_body(x), node.get_nics().values()))
                a += ',\n      nics: [ {}\n      ]\n'.format(nics)
            a += ' }'
            return a

        def wire_yaml_body(wire):
            if wire.is_n9_n9():
                comment = ' # peer-link'
            elif wire.is_n9_tor():
                comment = ' # uplink '
            else:
                comment = ''
            return '  {{from-node-id: {:7}, from-port-id: {:43}, from-mac: "{:17}", to-node-id: {:7}, to-port-id: {:22}, to-mac: "{:17}", pc-id: {:15}}}'.format(wire._from['node'].get_node_id(), wire._from['port-id'],
                                                                                                                                                                 wire._from['mac'],
                                                                                                                                                                 wire._to['node'].get_node_id(), wire._to['port-id'], wire._to['mac'],
                                                                                                                                                                 wire._pc_id) + comment

        with open('saved_lab_config.yaml', 'w') as f:
            f.write('lab-id: {} # integer in ranage (0,99). supposed to be unique in current L2 domain since used in MAC pools\n'.format(self.get_id()))
            f.write('lab-name: {} # any string to be used on logging\n'.format(self))
            f.write('lab-type: {} # supported types: {}\n'.format(self.get_type(), ' '.join(self.SUPPORTED_TYPES)))
            f.write('description-url: "{}"\n'.format(self))
            f.write('\n')
            f.write('dns: {}\n'.format(self.get_dns()))
            f.write('ntp: {}\n'.format(self.get_ntp()))
            f.write('\n')
            f.write('# special creds to be used by OS neutron services\n')
            f.write('special-creds: {{neutron_username: {}, neutron_password: {}}}\n'.format(self._neutron_username, self._neutron_password))
            f.write('\n')
    
            f.write('networks: [\n')
            net_bodies = [net_yaml_body(net=x) for x in self.get_all_nets().values()]
            f.write(',\n'.join(net_bodies))
            f.write('\n]\n\n')
    
            f.write('switches: [\n')
            node_bodies = [node_yaml_body(node=x, tp=switch) for x in self.get_switches()]
            f.write(',\n'.join(node_bodies))
            f.write('\n]\n\n')
    
            f.write('nodes: [\n')
            node_bodies = [node_yaml_body(node=x, tp=others) for x in self.get_servers_with_nics() if not isinstance(x, VirtualServer)]
            f.write(',\n\n'.join(node_bodies))
            f.write('\n]\n\n')
    
            f.write('virtuals: [\n')
            node_bodies = [node_yaml_body(node=x, tp=virtual) for x in self.get_servers_with_nics() if isinstance(x, VirtualServer)]
            f.write(',\n\n'.join(node_bodies))
            f.write('\n]\n\n')
    
            f.write('wires: [\n')
            wires_body = [wire_yaml_body(wire=x) for x in self.get_all_wires() if x]
            f.write(',\n'.join(wires_body))
            f.write('\n]\n')
