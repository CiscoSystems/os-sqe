class Network(object):
    def __init__(self, lab, net_id, cidr, vlan, mac_pattern, is_via_tor=False, is_pxe=False):
        from netaddr import IPNetwork

        self._lab = lab
        self._net = IPNetwork(cidr)
        self._net_id = net_id
        self._vlan = vlan  # single network needs to sit on single vlan
        self._mac_pattern = mac_pattern
        self._is_pxe = is_pxe  # NICs on this network will be configured as PXE enabled
        self._is_via_tor = is_via_tor  # this network if supposed to go out of lab's TOR

    def __repr__(self):
        return u'net: {} {} {}'.format(self._net_id, self._net, self._vlan)

    @staticmethod
    def add_network(lab, net_id, net_desc):
        """Fabric to create a class Nic instance
        :param lab: class Laboratory instance
        :param net_id: short string id of this network, also see nic_id in class Nic
        :param net_desc: dictionary e.g. {vlan: 319,  mac-pattern: AA, cidr: 10.23.221.128/26, is-via-tor: True }
        :returns class Network instance
        """

        try:
            return Network(lab=lab, net_id=net_id, cidr=net_desc['cidr'], vlan=str(net_desc['vlan']), mac_pattern=net_desc['mac-pattern'], is_via_tor=net_desc.get('is-via-tor', False), is_pxe=net_desc.get('is-pxe', False))
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

    def is_pxe(self):
        return self._is_pxe

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
    def __init__(self, nic_id, node, ip, on_wires, is_ssh):

        self._net = node.lab().get_net(nic_id)    # valid lab.network.Network
        self._net.check_ip_correct(msg='{}: nic "{}" has problem: '.format(node, nic_id), ip=ip)

        self._node = node  # nic belongs to the node
        self._names = []  # this is NIC name which coincides with network name
        self._ip = ip  # might be also not int but a sting which says that ip for this NIC is not yet available
        self._on_wires = on_wires  # this NIC sits on this list of wires, usually 2 for port channel and 1 for PXE boot via LOM
        self._macs = []
        self._port_ids = []
        self._is_ssh = is_ssh

        for wire in self._on_wires:
            wire.add_nic(self)
            own_port_id = wire.get_own_port(node)
            self._port_ids.append(own_port_id)
            self._is_on_lom = own_port_id in ['LOM-1', 'LOM-2']
            mac = wire.get_mac()
            mac = mac[:-2] + str(self._net.get_mac_pattern()) if own_port_id not in ['LOM-1', 'LOM-2'] else mac
            self._macs.append(mac)
            if len(self._on_wires) == 1:
                self._names = [nic_id]  # if nic sits on single wire, nic names has just a single value coinciding with given name
            else:
                self._names.append(nic_id + ('0' if own_port_id in ['MLOM/0', 'LOM-1'] else '1'))

    def __repr__(self):
        return u'{} {} {}'.format(self.get_ip_with_prefix(), self.get_names(), self.get_macs())

    @staticmethod
    def add_nic(node, nic_id, nic_desc):
        """Fabric to create a class Nic instance
        :param node: class LabServer instance
        :param nic_id: short string id of this NIC, must be the same as corresponding net_id of class Network
        :param nic_desc: dictionary e.g. {'ip': '10.23.221.142', 'port': '37', 'is_ssh': True}
        :returns class Nic instance
        """
        try:
            ports = nic_desc['ports']
            on_wires = [x for x in node.get_all_wires() if x.get_own_port(node) in ports]  # filter all wires of the node which has the same port as this NIC
            if not on_wires and not node.is_virtual():
                raise ValueError('{}: NIC "{}" tries to sit on non existing ports: {}'.format(node, nic_id, ports))
            return Nic(nic_id=nic_id, node=node, ip=nic_desc['ip'], on_wires=on_wires, is_ssh=nic_desc.get('is_ssh', False))
        except KeyError as ex:
            raise ValueError('{}: nic "{}" does not specify {}'.format(node, nic_id, ex))

    def is_pxe(self):
        return self._net.is_pxe()

    def is_on_lom(self):
        return self._is_on_lom

    def is_ssh(self):
        return self._is_ssh

    def get_names(self):
        return self._names

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

    def get_macs(self):
        return self._macs

    def get_port_ids(self):
        return self._port_ids

    def get_yaml_body(self):
        ports = [x.get_own_port(self) for x in self._on_wires]
        return '{:6}: {{ip: {:10}, ports: {} }}'.format(self._names[0][:-1] if len(self._names) > 1 else self._names[0], self.get_ip_and_mask()[0], ports)
