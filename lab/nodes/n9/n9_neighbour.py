class N9neighbourLLDP(object):
    def __init__(self, n9, dic):
        self.n9 = n9
        self._dic = dic

    def __repr__(self):
        return u'{} {} {}'.format(self.n9, self.chassis_id, self.mac)

    @property
    def chassis_id(self):
        return self._dic.get('chassis_id', '010101010101').replace('.', '')

    @property
    def mac(self):
        return self._dic['port_id'].replace('.', '')

    @property
    def port(self):
        return self.n9.ports.get(self._dic['l_port_id'].replace('Eth', 'Ethernet'))

    @staticmethod
    def process_n9_answer(n9, answer):
        lst = answer['TABLE_nbor_detail']['ROW_nbor_detail']  # lldp returns dict
        return [N9neighbourLLDP(n9=n9, dic=x) for x in lst]

    @staticmethod
    def shift_mac_by(mac, shift):
        m = mac.replace(':', '').replace('.', '').strip().lower()
        return '{:012x}'.format(int(m, 16) + shift)

    @staticmethod
    def find_with_mac(mac, cimc_port_id, neighbours):
        """ adaptor-MLOM/ext-eth-0  with mac '54:A2:74:CC:A9:70' reported by lldp as 54a2.74cc.a970       Eth1/4          120                    54a2.74cc.a974
            adaptor-MLOM/ext-eth-1  with mac '54:A2:74:CC:A9:71' reported by lldp as 54a2.74cc.a970       Eth1/4          120                    54a2.74cc.a978
            sys/rack-unit-1/network-adapter-1/eth-3: '3c:fd:fe:a5:fd:90' reported by lddp as 3cfd.fea5.fd90       Eth1/12         121                    3cfd.fea5.fd90 
        """
        if '-MLOM/ext-eth-0' in cimc_port_id:
            shift = 4
        elif 'MLOM/ext-eth-1' in cimc_port_id:
            shift = 7
        else:
            shift = 0
        n9_mac = N9neighbourLLDP.shift_mac_by(mac=mac, shift=shift)
        chassis_id = N9neighbourLLDP.shift_mac_by(mac=mac, shift=-1 if 'MLOM/ext-eth-1' in cimc_port_id else 0)

        found = [x for x in neighbours if n9_mac == x.mac and chassis_id == x.chassis_id]
        assert len(found) <= 1, 'More then 1 neighbour with the same MAC on {}'.format(found[0].n9)
        return found[0] if found else None


class N9neighbourCDP(object):
    def __init__(self, n9, dic):
        self.n9 = n9
        self.dic = dic

    def __repr__(self):
        return u'{} {} {} {} {}'.format(self.n9, self.port_id, self.device_id, self.peer_port_id, self.ipv4)

    @property
    def ipv4(self):
        return self.dic.get('v4mgmtaddr', 'NoIP')

    @property
    def port_id(self):
        return self.dic['intf_id']

    @property
    def device_id(self):
        return self.dic['device_id']

    @property
    def pc_id(self):
        return self.n9.ports[self.port_id].pc_id if self.port_id != 'mgmt0' else None

    @property
    def peer_port_id(self):
        return self.dic['port_id']

    @staticmethod
    def process_n9_answer(n9, answer):
        return [N9neighbourCDP(n9=n9, dic=x) for x in answer]  # sh cdp  nei returns list
