class N9neighbour(object):
    def __init__(self, n9, dic):
        self.n9 = n9
        self._dic = dic

    @property
    def macs(self):
        return [self._dic.get('chassis_id', 'No_chassis_id'), self._dic['port_id']]

    @property
    def port(self):
        return self.n9.ports[self._dic['l_port_id'].replace('Eth', 'Ethernet')]

    @staticmethod
    def process_n9_answer(n9, answer):
        lst = answer['TABLE_nbor_detail']['ROW_nbor_detail'] if type(answer) is not list else answer  # cdp retunrs list, lldp returns dict
        return [N9neighbour(n9=n9, dic=x) for x in lst]

    @staticmethod
    def mac_n9_to_normal(m):
        return ':'.join([m[0:2], m[2:4], m[5:7], m[7:9], m[10:12], m[12:14]]).upper()  # 54a2.74cc.7f42 -> 54:A2:74:CC:7F:42

    @staticmethod
    def mac_normal_to_n9(m):
        return '.'.join([m[0:2] + m[3:5], m[6:8] + m[9:11], m[12:14] + m[15:]]).lower()  # 54:A2:74:CC:7F:42 -> 54a2.74cc.7f42

    @staticmethod
    def find_with_mac(mac, neighbours):
        if ':' in mac:
            mac = N9neighbour.mac_normal_to_n9(m=mac)
        found = [x for x in neighbours if mac in x.macs]
        assert len(found) <= 1, 'More then 1 neighbour with the same MAC'
        return found[0] if found else None