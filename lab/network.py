class Network(object):
    def __init__(self, pod, net_id, cidr, vlan, is_via_tor, roles_must_present):
        from netaddr import IPNetwork

        self.pod = pod
        self.net = IPNetwork(cidr)
        self.id = net_id
        self.vlan = vlan  # single network needs to sit on single vlan
        self.is_via_tor = is_via_tor  # this network if supposed to go out of lab's TOR
        self.roles_must_present = roles_must_present  # list of node's roles which should sit on this network

    def __repr__(self):
        return u'net: {} {} {}'.format(self.id, self.net, self.vlan)

    @staticmethod
    def add_network(pod, dic):
        """Fabric to create a class Nic instance
        :param pod: object of lab.laboratory.Laboratory
        :param dic: dictionary e.g. {id: a, vlan: 319,  cidr: 10.23.221.128/26, is-via-tor: True }
        :returns class Network instance
        """

        try:
            return Network(pod=pod, net_id=dic['id'], cidr=dic['cidr'], vlan=dic['vlan'], is_via_tor=dic['is-via-tor'], roles_must_present=dic['roles'])
        except KeyError as ex:
            raise ValueError('Network "id: {}" does not specify key {}'.format(dic.get('id', dic), ex))

    @staticmethod
    def add_networks(pod, nets_cfg):
        return {x['id']: Network.add_network(pod=pod, dic=x) for x in nets_cfg}

    def get_ip_for_index(self, index):
        try:
            return self.net[index]
        except IndexError:
            raise ValueError('{}: Index {} is out of this network the max is {} = {}'.format(self, index, self.net.size, self.net[self.net.size-1]))

    def check_ip_correct(self, msg, ip):
        import netaddr

        try:
            if ip in self.net:
                if [x for x in [0, 1, 2, 3, -1] if str(self.net[x]) == ip]:
                    raise ValueError('{} ip="{}" coincides with either network address broadcast address or gateway hsrp triple'.format(msg, ip))
            else:
                raise ValueError('{} ip="{}" does not belong to "{}"'.format(msg, ip, self.net))

        except netaddr.AddrFormatError:
            raise ValueError('{} ip="{}" is not a valid ip'.format(msg, ip))


class Nic(object):
    def __init__(self, nic_id, node, ip, is_ssh):

        try:
            self.net = node.pod.networks[nic_id]    # valid lab.network.Network
        except KeyError:
            raise ValueError('{}: trying to create NIC on network "{}" which does not exist'.format(node, nic_id))
        # self._net.check_ip_correct(msg='{}: nic "{}" has problem: '.format(node, nic_id), ip=ip) TODO remove when fix the problem in c25bot

        self.node = node  # nic belongs to the node
        self.id = nic_id  # this is NIC name which coincides with network name
        self.ip = ip  # might be also not int but a string which says that ip for this NIC is not yet available
        self.is_ssh = is_ssh

    # def associate_with_wires(self, wires):
    #     for wire in wires:
    #         wire.add_nic(self)
    #         own_port_id = wire.get_own_port(self._node)
    #         own_mac = wire.get_own_mac(self._node)
    #         self._port_ids.append(own_port_id)
    #         self._is_on_lom = own_port_id in ['LOM-1', 'LOM-2']
    #         mac = wire.get_mac()
    #         mac = mac[:-2] + str(self._net.get_mac_pattern()) if own_port_id not in ['LOM-1', 'LOM-2'] else mac
    #         self._macs.append(mac)
    #         if len(self._on_wires) == 1:
    #             self._names = [nic_id]  # if nic sits on single wire, nic names has just a single value coinciding with given name
    #         else:
    #             self._names.append(nic_id + ('0' if own_port_id in ['MLOM/0', 'LOM-1'] else '1'))

    def __repr__(self):
        return u'{} {}'.format(self.ip_with_prefix, self.id)

    @staticmethod
    def create_nic(node, dic):
        """Fabric to create Nic()
        :param node: object of class derived from LabServer
        :param dic: dict e.g. {'nic-id': XX, 'ip': XX, 'ports': [XXX, XXX], 'is_ssh': True}
        :returns Nic()
        """
        try:
            return Nic(nic_id=dic['id'], node=node, ip=dic['ip'], is_ssh=dic['is-ssh'])
        except KeyError as ex:
            raise ValueError('{}: nic "{}" does not specify {}'.format(node, dic, ex))

    @staticmethod
    def create_nics_dic(node, dics_lst):
        """Fabric to create a dict of Nic()
        :param node:
        :param dics_lst: list of dicts
        :return: {'nic_id': Nic(), ...}
        """
        return {dic['id']: Nic.create_nic(node=node, dic=dic) for dic in dics_lst}

    @property
    def ip_and_mask(self):
        return str(self.ip), str(self.net.get_netmask())

    @property
    def ip_with_prefix(self):
        return self.ip + '/' + self.net.net.size

    @property
    def gw(self):
        return self.net.gw

    @property
    def gw_with_prefix(self):
        return self.gw + '/' + self.net.net.size

    @property
    def vlan_id(self):
        return self.net.vlan_id
