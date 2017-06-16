from lab.nodes.n9.n9_neighbour import N9neighbour
from lab.nodes.n9.n9_port import N9Port
from lab.nodes.n9.n9_port_channel import N9PortChannel
from lab.nodes.n9.n9_vlan import N9Vlan
from lab.nodes.n9.n9_vpc_domain import N9VpcDomain
from lab.nodes.n9.n9_vlan_port import N9VlanPort


class N9Status(object):
    def handle_port(self, pc_id, port_id, port_name, port_mode, vlans):
        try:
            port = self._port_dic[port_id]
            port.handle(pc_id=pc_id, port_name=port_name, port_mode=port_mode, vlans=vlans)
        except KeyError:
            raise ValueError('{}: does not have port "{}", check your configuration'.format(self._n9, port_id))

    def handle_pc(self, pc_id, pc_name, pc_mode):
        cmd_make = ['conf t', 'int ' + pc_id, 'desc ' + pc_name, 'mode ' + pc_mode]
        cmd_name = ['conf t', 'int ' + pc_id, 'desc ' + pc_name]
        cmd_mode = ['conf t', 'int ' + pc_id, 'mode ' + pc_mode]
        try:
            a_name = self._pc_dic[pc_id].get_name()
            self.fix_problem(cmd=cmd_name, msg='{} has actual description "{}" while requested is "{}"'.format(pc_id, a_name, pc_name))
            a_mode = self._pc_dic[pc_id].get_mode()
            if a_mode != pc_mode:
                self.fix_problem(cmd=cmd_mode, msg='{} has actual mode "{}" while requested is "{}"'.format(pc_id, a_mode, pc_mode))
        except KeyError:
            self.fix_problem(cmd=cmd_make, msg='no port-channel "{}"'.format(pc_id))

        # actual = self.n9_show_all()
        # for port_id in port_ids:
        #     self.n9_configure_port(pc_id=pc_id, port_id=port_id, vlans_string=vlans_string, desc=desc, mode=mode)
        #
        # actual_port_ids = actual['ports'].get(str(pc_id), [])
        # if actual_port_ids:  # port channel with this id already exists
        #     if port_ids != actual_port_ids:  # make sure that requested list of port-ids equals to actual list
        #         raise RuntimeError('{}: port-channel {} has different list of ports ({}) then requested ({})'.format(self, pc_id, actual_port_ids, port_ids))
        #     self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'switchport {} vlan {}'.format('trunk allowed' if mode == 'trunk' else 'access', vlans_string)])
        # else:  # port channel is not yet created
        #     self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'descr {0}'.format(desc), 'switchport', 'switchport mode ' + mode, 'switchport {} vlan {}'.format('trunk allowed' if mode == 'trunk' else 'access',
        #                                                                                                                                                                 vlans_string)])
        #
        #     if is_peer_link_pc:
        #         self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'vpc peer-link'], timeout=180)
        #     else:
        #         self.cmd(['conf t', 'int port-channel {0}'.format(pc_id), 'spanning-tree port type edge {}'.format('trunk' if mode == 'trunk' else ''), 'shut', 'no lacp suspend-individual', 'no shut'], timeout=180)
        #
        #     for port_id in port_ids:  # add ports to the port-channel
        #         self.cmd(['conf t', 'int ethernet ' + port_id, 'channel-group {0} force mode active'.format(pc_id)])



    def fix_problem(self, cmd, msg):
        from fabric.operations import prompt
        import time

        self._n9.log('{} do: {}'.format(msg, ' '.join(cmd)))
        time.sleep(1)  # prevent prompt message interlacing with log output
        if prompt('say y if you want to fix it: ') == 'y':
            self._n9.n9_cmd(cmd)