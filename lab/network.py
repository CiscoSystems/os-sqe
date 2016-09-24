class Network(object):
    def __init__(self, name, cidr, vlan, mac_pattern):
        from netaddr import IPNetwork

        self._net = IPNetwork(cidr)
        self._name = name
        self._vlan = vlan  # single network needs to sit on single vlan
        self._mac_pattern = mac_pattern
        self._is_pxe = False  # NICs on this network will be configured as PXE enabled
        self._is_ssh = False  # Credentials on this network will be used to ssh to servers
        self._is_vts = False  # VTS components will be deployed on this network, if requested
        self._is_via_tor = False  # this network if supposed to go our of lab's TOR

    def __repr__(self):
        return u'net: {} {} {}'.format(self._name, self._net, self._vlan)

    def get_name(self):
        return self._name

    def get_vlan(self):
        return self._vlan

    def get_mac_pattern(self):
        return self._mac_pattern

    def get_gw(self):
        return self._net[1]

    def is_pxe(self):
        return self._is_pxe

    def set_is_pxe(self):
        self._is_pxe = True

    def is_ssh(self):
        return self._is_ssh

    def set_is_ssh(self):
        self._is_ssh = True

    def is_vts(self):
        return self._is_vts

    def set_is_vts(self):
        self._is_vts = True

    def set_is_via_tor(self):
        self._is_via_tor = True

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


class Nic(object):
    def __init__(self, name, node, net, net_index, on_wires):
        self._node = node  # nic belongs to the node
        self._name = name  # this is NIC name which coincides with network name
        self._net = net    # valid lab.network.Network
        self._net_index = net_index  # might be also not int but a sting which says that ip for this NIC is not yet available
        self._on_wires = on_wires  # this NIC sits on this list of wires, usually 2 for port channel and 1 for PXE boot via LOM

        for wire in self._on_wires:
            own_port_id = wire.get_own_port(node)
            self._is_on_lom = own_port_id in ['LOM-1', 'LOM-2']
            wire.correct_mac_by_net_info(self._net)

    def __repr__(self):
        return u'{} on {}'.format(self._on_wires, self._net)

    def is_pxe(self):
        return self._net.is_pxe()

    def is_on_lom(self):
        return self._is_on_lom

    def is_vts(self):
        return self._net.is_vts()

    def is_ssh(self):
        return self._net.is_ssh()

    def get_slave_nics(self):
        return self._slave_nics

    def get_name(self):
        return self._name

    def get_ip_and_mask(self):
        """ Not all NICs has any ip assigned, usually this ip will be decided later based on the info which is not available during deployment
            So one cat get instead of IP the string which describes  this situation.

        :return: tuple of (ip, netmask)
        """
        ip = self._net.get_ip_for_index(self._net_index) if type(self._net_index) is int else self._net_index
        return str(ip), str(self._net.get_netmask())

    def get_ip_with_prefix(self):
        return '{}/{}'.format(self.get_ip_and_mask()[0], self._net.get_prefix_len())

    def get_net(self):
        return self._net

    def get_gw(self):
        return self._net.get_gw()

    def get_gw_with_prefix(self):
        return '{}/{}'.format(self.get_gw(), self._net.get_prefix_len())

    def is_bond(self):
        return len(self._on_wires) > 1  # NIC sits on 2 wires, meaning this is bond

    def get_vlan(self):
        return self._net.get_vlan()

    def get_mac(self):
        return self._mac

    def get_yaml_body(self):
        return '{:6}: {{ip: {:20}, port: {:5}}}'.format(self._name, self.get_ip_and_mask()[0], self._on_wires[0].get_pc_id())
