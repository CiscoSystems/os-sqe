from lab.nodes.n9.n9_port import N9Port


class N9PortChannel(N9Port):
    def __init__(self, n9, sh_int_st_dic, sh_int_br_dic, sh_pc_sum_dic, sh_vpc_dic):
        super(N9PortChannel, self).__init__(n9=n9, sh_int_st_dic=sh_int_st_dic, sh_int_br_dic=sh_int_br_dic)

        self.pc = self
        self.n9 = n9
        self.sh_pc_sum_dic = sh_pc_sum_dic
        self.sh_vpc_dic = sh_vpc_dic

        self.ports = []
        lst = self.sh_pc_sum_dic['TABLE_member']['ROW_member'] # it's a list of dicts if few ports in this pc or just a dict if single port in this pc
        lst = [lst] if type(lst) is dict else lst
        for x in lst:  # list of N9Ports belonging to this port-channel
            port = n9.ports[x['port']]
            port.pc = self
            self.ports.append(port)

    @property
    def pc_id(self):
        return self.sh_pc_sum_dic['port-channel']

    # def n9_configure_vpc(self):
    #     vpc = self._requested_topology['vpc']
    #     for pc_id, info in vpc.items():
    #         self.n9_create_port_channel(pc_id=pc_id, desc=info['description'], port_ids=info['ports'], mode=info['mode'], vlans_string=info['vlans'])
    #         if self.get_peer_link_wires():
    #             self.n9_create_vpc(pc_id)
    # def handle_vpc_domain(self, peer_ip, domain_id=1):
    #    self.n9.n9_cmd(['conf t', 'feature vpc'])
    #    self.n9.n9_cmd(['conf t', 'vpc domain {0}'.format(domain_id), 'peer-keepalive destination {0}'.format(peer_ip)], timeout=60)

    # def n9_configure_peer_link(self):
    #     peer_link = self._requested_topology['peer-link']
    #     ip = peer_link['ip']
    #     if ip:
    #         pc_id = peer_link['pc-id']
    #         desc = peer_link['description']
    #         port_ids = peer_link['ports']
    #         vlans_string = peer_link['vlans']
    #         self.n9_configure_vpc_domain(peer_ip=ip)
    #         self.n9_create_port_channel(pc_id=pc_id, desc=desc, port_ids=port_ids, vlans_string=vlans_string, mode='trunk', is_peer_link_pc=True)

    @staticmethod
    def check_create(n9, pc_id, desc, mode, vlans):
        if pc_id not in n9.port_channels:
            n9.log('Creating ' + pc_id)
            cmd = ['conf t', 'int port-channel ' + pc_id, 'desc ' + desc, 'vpc ' + pc_id, 'no shut']
            n9.n9_fix_problem(cmd=cmd, msg='no port channel {}, create'.format(pc_id))
        else:
            pc = n9.port_channels[pc_id]
            n9.log('Checking {} {}'.format(pc_id, desc))
            if pc.name != desc:
                cmd = ['conf t', 'int ' + pc_id, 'desc ' + desc]
                n9.fix_problem(cmd=cmd, msg='{} has actual description "{}" while requested is "{}"'.format(pc, pc.name, desc))
            if pc.mode != mode:
                cmd = ['conf t', 'int ' + pc_id, 'switchport mode ' + mode]
                n9.fix_problem(cmd=cmd, msg='{} has actual mode "{}" while requested is "{}"'.format(pc, pc.mode, mode))
