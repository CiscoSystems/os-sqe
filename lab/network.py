from netaddr import IPNetwork


class Network(IPNetwork):
    def __init__(self, name, cidr, is_ssh, vlan, mac_pattern):
        super(Network, self).__init__(cidr)
        self._name = name
        self._is_ssh = is_ssh
        self._vlan = vlan  # single network needs to sit on single vlan
        self._mac_pattern = mac_pattern

    def get_name(self):
        return self._name

    def is_ssh(self):
        return self._is_ssh

    def get_vlan(self):
        return self._vlan

    def get_mac_pattern(self):
        return self._mac_pattern


class Nic(object):
    def __repr__(self):
        ip, mask = self.get_ip_and_mask()
        return u'name={} mac={} ip={} mask={}'.format(self._name, self._mac, ip, mask)

    def __init__(self, name, mac, node, net, net_index, on_wires):
        self._node = node  # nic belongs to the node
        self._name = name  # this is NIC name which coincides with network name
        self._net = net    # valid lab.network.Network
        self._net_index = net_index  # might be also not int but a sting which says that ip for this NIC is not yet available
        self._mac = mac    # valid mac address
        self._on_wires = on_wires  # this NIC sits on this list of wires, usually 2 for port channel and 1 for PXE boot via LOM

    def get_mac(self):
        return self._mac

    def get_name(self):
        return self._name

    def get_ip_and_mask(self):
        """ Not all NICs has any ip assigned, usually this ip will be decided later based on the info which is not available during deployment
            So one cat get instead of IP the string which describes  this situation.

        :return: tuple of (ip, netmask)
        """
        ip = self._net[self._net_index] if type(self._net_index) is int else self._net_index
        return str(ip), str(self._net.netmask)

    def is_ssh(self):
        return self._net.is_ssh()

    def get_net(self):
        return self._net

    def is_bond(self):
        return len(self._on_wires) == 2  # NIC sits on 2 wires, meaning this is bond

    def get_vlan(self):
        return self._net.get_vlan()

    def get_wires(self):
        return self._on_wires
