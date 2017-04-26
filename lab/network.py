class Network(object):
    def __init__(self, lab, net_id, cidr, vlan, roles_must_present, is_via_tor):
        from netaddr import IPNetwork

        self._lab = lab
        self._net = IPNetwork(cidr)
        self._net_id = net_id
        self._vlan = vlan  # single network needs to sit on single vlan
        self._is_via_tor = is_via_tor  # this network if supposed to go out of lab's TOR
        self._roles_on_this_net = roles_must_present  # list of node's roles which should sit on this network

    def __repr__(self):
        return u'net: {} {} {}'.format(self._net_id, self._net, self._vlan)

    def set_vlan(self, vlan_id):
        self._vlan = vlan_id

    def set_cidr(self, cidr):
        from netaddr import IPNetwork

        self._net = IPNetwork(cidr)

    def set_via_tor(self, is_via_tor):
        self._is_via_tor = is_via_tor

    @staticmethod
    def add_network(lab, net_id, net_desc):
        """Fabric to create a class Nic instance
        :param lab: class Laboratory instance
        :param net_id: short string id of this network, also see nic_id in class Nic
        :param net_desc: dictionary e.g. {vlan: 319,  mac-pattern: AA, cidr: 10.23.221.128/26, is-via-tor: True }
        :returns class Network instance
        """

        try:
            return Network(lab=lab, net_id=net_id, cidr=net_desc['cidr'], vlan=str(net_desc['vlan']), roles_must_present=net_desc['should-be'], is_via_tor=net_desc['is-via-tor'])
        except KeyError as ex:
            raise ValueError('network {} does not specify {}'.format(net_id, ex))

    def get_net_id(self):
        return self._net_id

    def get_vlan_id(self):
        return self._vlan

    def get_mac_pattern(self):
        return self._mac_pattern

    def get_gw(self):
        return self._net[1]

    def is_via_tor(self):
        return self._is_via_tor

    def get_ip_for_index(self, index):
        return self._net[index]

    def get_size(self):
        return self._net.size

    def get_prefix_len(self):
        return self._net.prefixlen

    def get_netmask(self):
        return self._net.netmask

    def get_cidr(self):
        return self._net.cidr

    def get_roles(self):
        return self._roles_on_this_net

    def check_ip_correct(self, msg, ip):
        import netaddr

        try:
            if ip in self._net:
                if [x for x in [0, 1, 2, 3, -1] if str(self._net[x]) == ip]:
                    raise ValueError('{} ip="{}" coincides with either network address broadcast address or gateway hsrp triple'.format(msg, ip))
            else:
                raise ValueError('{} ip="{}" does not belong to "{}"'.format(msg, ip, self._net))

        except netaddr.AddrFormatError:
            raise ValueError('{} ip="{}" is not a valid ip'.format(msg, ip))


class Nic(object):
    def __init__(self, nic_id, node, ip, is_ssh):

        try:
            self._net = node.lab().get_net(nic_id)    # valid lab.network.Network
        except KeyError:
            raise ValueError('{}: trying to create NIC on network "{}" which does not exeist'.format(node, nic_id))
        # self._net.check_ip_correct(msg='{}: nic "{}" has problem: '.format(node, nic_id), ip=ip) TODO remove when fix the problem in c25bot

        self._node = node  # nic belongs to the node
        self._nic_id = nic_id  # this is NIC name which coincides with network name
        self._ip = ip  # might be also not int but a sting which says that ip for this NIC is not yet available
        self._is_ssh = is_ssh

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
        return u'{} {}'.format(self.get_ip_with_prefix(), self._nic_id)

    @staticmethod
    def add_nic(node, nic_cfg):
        """Fabric to create a class Nic instance
        :param node: object of class LabServer or derived
        :param nic_cfg: dict e.g. {'nic-id': XX, 'ip': XX, 'ports': [XXX, XXX], 'is_ssh': True}
        :returns class Nic instance
        """
        try:
            return Nic(nic_id=nic_cfg['nic-id'], node=node, ip=nic_cfg['ip'], is_ssh=nic_cfg['is-ssh'])
        except KeyError as ex:
            raise ValueError('{}: nic "{}" does not specify {}'.format(node, nic_cfg, ex))

    @staticmethod
    def add_nics(node, nics_cfg):
        return {nic_cfg['nic-id']: Nic.add_nic(node=node, nic_cfg=nic_cfg) for nic_cfg in nics_cfg}

    def is_ssh(self):
        return self._is_ssh

    def get_ip_and_mask(self):
        return str(self.get_ip()), str(self._net.get_netmask())

    def get_ip(self):
        return self._ip

    def get_ip_with_prefix(self):
        return '{}/{}'.format(self.get_ip(), self._net.get_prefix_len())

    def get_net(self):
        return self._net

    def get_gw(self):
        return self._net.get_gw()

    def get_gw_with_prefix(self):
        return '{}/{}'.format(self.get_gw(), self._net.get_prefix_len())

    def get_vlan_id(self):
        return self._net.get_vlan_id()

    def get_nic_id(self):
        return self._nic_id
