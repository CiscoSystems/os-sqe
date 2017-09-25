class N9Vlan(object):
    NOT_YET = 'special name for not yet created vlan'

    def __init__(self, n9,  dic):
        self.n9 = n9
        self._dic = dic

    @property
    def vlan_name(self):
        return self._dic['vlanshowbr-vlanname']

    @property
    def vlan_id(self):
        return self._dic['vlanshowbr-vlanid']

    @property
    def port_ids(self):
        return self._dic.get('vlanshowplist-ifidx', [])

    def handle_vlan(self, vlan_name):
        self.n9.log('Checking vlan {} {}'.format(self.vlan_id, vlan_name))
        if self.vlan_name != vlan_name:
            msg = 'no vlan ' + self.vlan_id if self.vlan_name == self.NOT_YET else 'vlan {} has actual name {} while requested is {}'.format(self.vlan_id, self.vlan_name, vlan_name)
            self.n9.n9_fix_problem(cmd=['conf t', 'vlan ' + self.vlan_id, 'name ' + vlan_name, 'no shut'], msg=msg)
            self.vlan_name = vlan_name

    @staticmethod
    def create(n9, vlan_id):
        return N9Vlan(n9=n9, dic={'vlanshowbr-vlanname': 'not_yet_in_n9', 'vlanshowbr-vlanid': str(vlan_id)})

    @staticmethod
    def process_n9_answer(n9, answer):
        return {x['vlanshowbr-vlanid']: N9Vlan(n9=n9, dic=x) for x in answer['TABLE_vlanbrief']['ROW_vlanbrief']}
