from lab.nodes.n9 import N9


class VimTor(N9):
    TREX_MODE_CSR = 'access'
    TREX_MODE_NFVBENCH = 'trunck'

    def n9_border_leaf(self):
        vlans = self._requested_topology['vlans']
        tenant_vlan_ids = [vlan_id for vlan_id, name_and_others in vlans.items() if name_and_others['name'] == '{}-t'.format(self.pod)]
        if not tenant_vlan_ids:
            return  # this switch has no tenant vlan so do not configure border leaf on it

        tenant_vlan_id = tenant_vlan_ids[0]
        this_switch_bgp_nei_ip = '34.34.34.{}'.format(self._n)
        loopback_ip = '90.90.90.90'
        xrvr_bgp_ips = ['34.34.34.101', '34.34.34.102']
        self.cmd(['conf t', 'interface Vlan{}'.format(tenant_vlan_id), 'no shut', 'ip address {}/24'.format(this_switch_bgp_nei_ip), 'no ipv6 redirects', 'ip router ospf 100 area 0.0.0.0', 'hsrp 34 ', 'ip 34.34.34.100'],
                 timeout=60)
        self.cmd(['conf t', 'interface loopback0', 'ip address {}/32'.format(loopback_ip), 'ip address 92.92.92.92/32 secondary', 'ip router ospf 100 area 0.0.0.0'], timeout=60)
        self.cmd(['conf t', 'router ospf 100', 'router-id {}'.format(this_switch_bgp_nei_ip), 'area 0.0.0.0 default-cost 10'], timeout=60)
        self.cmd(['conf t', 'router bgp 23', 'router-id {}'.format(this_switch_bgp_nei_ip), 'address-family ipv4 unicast', 'address-family l2vpn evpn', 'retain route-target all',
                  'neighbor {}'.format(xrvr_bgp_ips[0]), 'remote-as 23', 'update-source Vlan{}'.format(tenant_vlan_id), 'address-family l2vpn evpn', 'send-community both',
                  'neighbor {}'.format(xrvr_bgp_ips[1]), 'remote-as 23', 'update-source Vlan{}'.format(tenant_vlan_id), 'address-family l2vpn evpn', 'send-community both'], timeout=60)

    def n9_trex_port(self, mode):
        pass
