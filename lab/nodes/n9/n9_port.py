class N9Port(object):
    def __init__(self, n9, pc_dic, n9_dic):
        self.n9 = n9
        self._dic = n9_dic
        self.pc = None

        if 'portchan' in n9_dic:
            self.pc = pc_dic['port-channel' + str(n9_dic['portchan'])]
            self.pc.add_port(self)

    @property
    def port_id(self):
        return self._dic['interface']

    @property
    def pc_id(self):
        return self.pc.pc_id if self.pc else None

    @property
    def mode(self):
        return self._dic['portmode']

    @property
    def speed(self):
        return self._dic['speed']

    @property
    def get_state(self):
        state = self._dic['state']
        return state if state == 'up' else self._dic['state_rsn_desc']

    @property
    def vlans(self):
        return self._dic['vlan'] if self.mode == 'access' else self._dic['vlan']  # TODO in trunk this field is always trunk

    @property
    def name(self):
        return self._dic.get('name', '--')  # for port with no description this field either -- or not in dict

    @property
    def is_not_connected(self):
        return self._dic['state_rsn_desc'] == u'XCVR not inserted'

    @property
    def is_down(self):
        return self._dic['state_rsn_desc'] == u'down'

    def handle(self, pc_id, port_name, port_mode, vlans):

        cmd_up = ['conf t', 'int ether ' + self.port_id, 'no shut']
        cmd_make = ['conf t', 'int ' + self.port_id, 'desc ' + port_name, 'switchport', 'switchport mode ' + port_mode, 'switchport {} vlan {}'.format('trunk allowed' if port_mode == 'trunk' else 'access', vlans)]
        cmd_name = ['conf t', 'int ' + self.port_id, 'desc ' + port_name]
        if self.is_not_connected:
            raise RuntimeError('N9K {}: Port {} seems to be not connected. Check your configuration'.format(self, self.port_id))
        a_pc_id = self.pc_id
        if a_pc_id is None:
            self.n9.fix_problem(cmd=cmd_make, msg='port {} is not a part of any port channels'.format(self.port_id))
        elif a_pc_id != pc_id:
            raise RuntimeError('N9K {}: Port {} belongs to different port-channel {}. Check your configuration'.format(self, self.port_id, a_pc_id))

        if self.is_down:
            self.n9.fix_problem(cmd=cmd_up, msg='{} is down'.format(self.port_id))

        a_name = self.name
        if a_name != port_name:
            self.n9.fix_problem(cmd=cmd_name, msg='{} has actual description "{}" while requested is "{}"'.format(self.port_id, a_name, port_name))
