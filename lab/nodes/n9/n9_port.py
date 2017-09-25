class N9Port(object):
    def __init__(self, n9, sh_int_st_dic, sh_int_br_dic):
        self.n9 = n9
        self.sh_int_st_dic = sh_int_st_dic
        self.sh_int_br_dic = sh_int_br_dic

        self.pc = None
        self.vlans = []  # list of N9Vlans assigned to this port


    def __repr__(self):
        return str(self.n9) + ' ' + self.port_id + ' ' + self.name + ' ' + self.mode

    @property
    def port_id(self):
        return self.sh_int_st_dic['interface']

    @property
    def pc_id(self):
        return self.pc.pc_id if self.pc else None

    @property
    def mode(self):
        return self.sh_int_br_dic['portmode']

    @property
    def speed(self):
        return self.sh_int_br_dic['speed']

    @property
    def state(self):
        return self.sh_int_st_dic['state'] if self.sh_int_br_dic['state'] == 'up' else self.sh_int_br_dic['state_rsn_desc']

    @property
    def name(self):
        return self.sh_int_st_dic.get('name', '--')  # for port with no description this field either -- or not in dict

    @property
    def is_not_connected(self):
        return self.sh_int_br_dic['state_rsn_desc'] == u'XCVR not inserted'

    @property
    def is_down(self):
        return self.sh_int_br_dic['state_rsn_desc'] == u'down'

    def check(self, pc_id, port_name, port_mode, vlans):
        should_be = self.port_id + ' ' + port_name + ' ' + self.mode + ' in ' + str(pc_id)

        self.n9.log('Checking {} should be {}'.format(self, should_be))

        if self.pc_id != pc_id:
            raise RuntimeError('{}: Port {} belongs to different port-channel {}. Check your configuration'.format(self.n9, self.port_id, self.pc_id))

        if self.name != port_name:
            cmd = ['conf t', 'int ' + self.port_id, 'desc ' + port_name]
            self.n9.fix_n9_problem(cmd=cmd, msg='{} has actual description "{}" while requested is "{}"'.format(self.port_id, self.name, port_name))
        if vlans is None:  # this means we don't no anything about this port just describe it as XXX for reference
            return

        if self.is_not_connected:
            raise RuntimeError('N9K {}: Port {} seems to be not connected. Check your configuration'.format(self, self.port_id))

        if self.is_down:
            cmd = ['conf t', 'int ether ' + self.port_id, 'no shut']
            self.n9.fix_problem(cmd=cmd, msg='{} is down'.format(self.port_id))

        if self.mode != port_mode:
            cmd = ['conf t', 'int ' + self.port_id, 'switchport mode ' + port_mode]
            self.n9.fix_n9_problem(cmd=cmd, msg='port {} is of type {}'.format(self.port_id, port_mode))

#            cmd_make = ['conf t', 'int ' + self.port_id, 'desc ' + port_name, 'switchport', 'switchport mode ' + port_mode, 'switchport {} vlan {}'.format('trunk allowed' if port_mode == 'trunk' else 'access', vlans)]

